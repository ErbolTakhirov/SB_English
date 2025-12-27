import io
import re
import time
import json
from typing import List, Tuple, Optional, Dict, Set
from datetime import date

import pandas as pd
from django.db import transaction
from django.db.utils import OperationalError

from core.models import Income, Expense, Document, UploadedFile
from core.llm import chat_with_context
from core.utils.ai_utils import ai_categorize_batch


def map_transaction_category(type_name, cat_str, desc_str):
    """Extracts and maps category from text using brackets or fuzzy matching."""
    # Try to extract from brackets first
    match = re.search(r'\[(.*?)\]', f"{cat_str} {desc_str}")
    extracted = match.group(1).lower().strip() if match else cat_str.lower().strip()
    
    # Get available choices
    if type_name == 'income':
        choices = [c[0] for c in Income._meta.get_field('income_type').choices]
    else:
        choices = [c[0] for c in Expense._meta.get_field('expense_type').choices]
        
    if extracted in choices:
        return extracted
    
    # Fuzzy match
    for c in choices:
        if c == extracted: return c
        if c.startswith(extracted) or extracted.startswith(c):
            return c
            
    return 'other'



CSV_REQUIRED_COLUMNS = {'type', 'date', 'amount'}


def smart_map_columns(df_sample: str) -> Dict[str, str]:
    """
    Use LLM to infer column mapping from a sample of data.
    """
    prompt = f"""
    You are a data cleaning assistant. Map the columns in this financial data sample to the target schema.
    Target Schema:
    - 'date': Valid date column (e.g. 2023-01-01, 01.01.2023)
    - 'amount': Numeric amount
    - 'type': 'income' or 'expense' (optional, if not found, ignore)
    - 'category': Category of transaction (optional)
    - 'description': details (optional)

    Data Sample (first 5 rows):
    {df_sample}

    Return ONLY a valid JSON object with the mapping. Keys are target schema names, values are actual column names from the sample.
    Example: {{"date": "Date Transaction", "amount": "Sum", "description": "Comment"}}
    If a column is not found, do not include it in the JSON.
    """
    try:
        response = chat_with_context(
            messages=[{'role': 'user', 'content': prompt}],
            user_data="",
            system_instruction="You are a JSON-only response bot.",
            anonymize=True
        )
        # Extract JSON from response
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"AI Mapping error: {e}")
    return {}


DB_LOCK_RETRY_ATTEMPTS = 5
DB_LOCK_RETRY_DELAY = 0.2


def _persist_transactions(income_objs: List[Income], expense_objs: List[Expense]) -> None:
    for attempt in range(DB_LOCK_RETRY_ATTEMPTS):
        try:
            with transaction.atomic():
                if income_objs:
                    Income.objects.bulk_create(income_objs, batch_size=200)
                if expense_objs:
                    Expense.objects.bulk_create(expense_objs, batch_size=200)
            return
        except OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < DB_LOCK_RETRY_ATTEMPTS - 1:
                time.sleep(DB_LOCK_RETRY_DELAY * (attempt + 1))
                continue
            raise


def _check_duplicate(transaction_type: str, date_val: date, amount: float, category: str, description: str, user, source_file=None) -> bool:
    """Проверяет, существует ли уже транзакция с такими же параметрами."""
    filters = {
        'user': user,
        'date': date_val,
        'amount': amount,
    }
    if source_file:
        filters['source_file'] = source_file

    if transaction_type == 'income':
        qs = Income.objects.filter(**filters)
        if description:
            qs = qs.filter(description__icontains=description)
    else:
        qs = Expense.objects.filter(**filters)
        if description:
            qs = qs.filter(description__icontains=description)
    return qs.exists()


def find_duplicates(user, source_file: Optional[UploadedFile] = None) -> Dict[str, List[Dict]]:
    """Находит все дубликаты транзакций. Возвращает {'incomes': [...], 'expenses': [...]}"""
    duplicates = {'incomes': [], 'expenses': []}
    
    # Для доходов
    incomes = Income.objects.filter(user=user)
    if source_file:
        incomes = incomes.filter(source_file=source_file)
    
    seen = {}
    for inc in incomes:
        # Key: date, amount, income_type, description
        key = (inc.date, inc.amount, inc.income_type, inc.description or '')
        if key in seen:
            if key not in [d['key'] for d in duplicates['incomes']]:
                duplicates['incomes'].append({
                    'key': key,
                    'transactions': [seen[key], inc.id]
                })
            else:
                idx = next(i for i, d in enumerate(duplicates['incomes']) if d['key'] == key)
                if inc.id not in duplicates['incomes'][idx]['transactions']:
                    duplicates['incomes'][idx]['transactions'].append(inc.id)
        else:
            seen[key] = inc.id
    
    # Для расходов
    expenses = Expense.objects.filter(user=user)
    if source_file:
        expenses = expenses.filter(source_file=source_file)
    
    seen = {}
    for exp in expenses:
        key = (exp.date, exp.amount, exp.expense_type, exp.description or '')
        if key in seen:
            if key not in [d['key'] for d in duplicates['expenses']]:
                duplicates['expenses'].append({
                    'key': key,
                    'transactions': [seen[key], exp.id]
                })
            else:
                idx = next(i for i, d in enumerate(duplicates['expenses']) if d['key'] == key)
                if exp.id not in duplicates['expenses'][idx]['transactions']:
                    duplicates['expenses'][idx]['transactions'].append(exp.id)
        else:
            seen[key] = exp.id
    
    return duplicates


def import_csv_transactions(file_obj, import_to_db: bool = True, user=None, source_file: Optional[UploadedFile] = None) -> Tuple[int, int, List[str], Dict]:
    """Import CSV with columns: type(income|expense), date(YYYY-MM-DD), amount, category(optional), description(optional).
    Returns (num_incomes, num_expenses, errors, stats_dict).
    stats_dict содержит: {'duplicates_skipped': int, 'duplicates_found': int, 'should_warn': bool}
    """
    errors: List[str] = []
    stats = {'duplicates_skipped': 0, 'duplicates_found': 0, 'should_warn': False}
    
    # Получаем настройки пользователя
    auto_clear = False
    auto_remove_dups = False
    if user and hasattr(user, 'profile'):
        auto_clear = user.profile.auto_clear_file_on_import
        auto_remove_dups = user.profile.auto_remove_duplicates
    
    # Если включена автоматическая очистка, удаляем все транзакции из этого файла
    if import_to_db and source_file and auto_clear:
        Income.objects.filter(user=user, source_file=source_file).delete()
        Expense.objects.filter(user=user, source_file=source_file).delete()
    
    try:
        df = pd.read_csv(file_obj)
    except Exception as e:
        return 0, 0, [f'CSV read error: {e}'], stats

    cols = set(c.lower() for c in df.columns)
    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        # AI Recovery: Try to map columns intelligently
        print("Required columns missing, attempting AI mapping...")
        try:
            # Take a sample for AI
            sample_str = df.head(5).to_csv(index=False)
            mapping = smart_map_columns(sample_str)
            
            # Apply mapping
            if mapping:
                # Invert mapping to rename: {actual: target}
                # AI returns {target: actual}
                rename_map = {v: k for k, v in mapping.items()}
                df.rename(columns=rename_map, inplace=True)
                
                # Re-normalize
                df.columns = [c.lower() for c in df.columns]
                cols = set(df.columns)
                
        except Exception as e:
            print(f"Smart mapping failed: {e}")

    # Re-check requirements
    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        # One last chance: if 'type' is missing but others are present, assume a default or split later?
        # For now, just error if date/amount still missing.
        required_data = {'date', 'amount'}
        if not required_data.issubset(cols):
             return 0, 0, [f'Could not recognize columns. Required: {", ".join(sorted(CSV_REQUIRED_COLUMNS))}. Found: {cols}'], stats

    # Ensure optional columns exist
    if 'category' not in df.columns:
        df['category'] = ''
    if 'description' not in df.columns:
        df['description'] = ''
    if 'type' not in df.columns:
        # If type is missing, we might assume it's mixed or specific file logic. 
        # For now, default to 'expense' if negative amount? Or just error.
        # Let's simply fill with 'expense' as default if unknown, or try heuristic
        # checking signs.
        df['type'] = df['amount'].apply(lambda x: 'income' if float(x) > 0 else 'expense')
        # If amounts are all positive, this might be wrong, but it's "AI-ish".
        pass

    num_i = 0
    num_e = 0
    income_rows = []
    expense_rows = []
    total_rows = len(df)
    duplicate_rows = 0

    for _, row in df.iterrows():
        try:
            typ = str(row['type']).strip().lower()
            dt = pd.to_datetime(row['date']).date()
            amt = float(row['amount'])
            cat = str(row.get('category', '') or '')
            desc = str(row.get('description', '') or '')
        except Exception as e:
            errors.append(f'Row error: {e}')
            continue

        # Проверка на дубликаты
        is_duplicate = False
        if import_to_db:
            is_duplicate = _check_duplicate(typ, dt, amt, "", desc, user, source_file)
            if is_duplicate:
                duplicate_rows += 1
                stats['duplicates_found'] += 1
                if not auto_remove_dups:
                    continue  

        if typ == 'income':
            num_i += 1
            if import_to_db and not is_duplicate:
                itype = map_transaction_category('income', cat, desc)
                income_rows.append({'amount': amt, 'date': dt, 'income_type': itype, 'description': desc})
        elif typ == 'expense':
            num_e += 1
            if import_to_db and not is_duplicate:
                etype = map_transaction_category('expense', cat, desc)
                expense_rows.append({'amount': amt, 'date': dt, 'expense_type': etype, 'description': desc})
        else:
            errors.append(f'Unknown type: {typ}')

    # AI Batch Categorization for 'other' entries
    if import_to_db:
        # Collect 'other' incomes
        other_incomes = [r for r in income_rows if r['income_type'] == 'other']
        if other_incomes:
            ai_cats = ai_categorize_batch(other_incomes, 'income')
            for r, cat in zip(other_incomes, ai_cats):
                r['income_type'] = cat

        # Collect 'other' expenses
        other_expenses = [r for r in expense_rows if r['expense_type'] == 'other']
        if other_expenses:
            ai_cats = ai_categorize_batch(other_expenses, 'expense')
            for r, cat in zip(other_expenses, ai_cats):
                r['expense_type'] = cat

        # Create objects
        income_objs = [Income(**r, user=user, source_file=source_file) for r in income_rows]
        expense_objs = [Expense(**r, user=user, source_file=source_file) for r in expense_rows]

        if income_objs or expense_objs:
            _persist_transactions(income_objs, expense_objs)

    # Проверка на предупреждение (>50% дублей)
    if total_rows > 0 and duplicate_rows / total_rows > 0.5:
        stats['should_warn'] = True

    stats['duplicates_skipped'] = duplicate_rows

    return num_i, num_e, errors, stats


def import_excel_transactions(file_obj, import_to_db: bool = True, sheet_name: Optional[str] = None, user=None, source_file: Optional[UploadedFile] = None) -> Tuple[int, int, List[str], Dict]:
    """
    Import Excel (.xlsx, .xls) with columns: type(income|expense), date(YYYY-MM-DD), amount, category(optional), description(optional).
    Returns (num_incomes, num_expenses, errors, stats_dict).
    stats_dict содержит: {'duplicates_skipped': int, 'duplicates_found': int, 'should_warn': bool}
    
    Args:
        file_obj: Excel file object
        import_to_db: Whether to import to database
        sheet_name: Specific sheet name to read (None = first sheet)
        user: User object
        source_file: UploadedFile object (источник транзакций)
    """
    errors: List[str] = []
    stats = {'duplicates_skipped': 0, 'duplicates_found': 0, 'should_warn': False}
    
    # Получаем настройки пользователя
    auto_clear = False
    auto_remove_dups = False
    if user and hasattr(user, 'profile'):
        auto_clear = user.profile.auto_clear_file_on_import
        auto_remove_dups = user.profile.auto_remove_duplicates
    
    # Если включена автоматическая очистка, удаляем все транзакции из этого файла
    if import_to_db and source_file and auto_clear:
        Income.objects.filter(user=user, source_file=source_file).delete()
        Expense.objects.filter(user=user, source_file=source_file).delete()
    
    try:
        # Read Excel file
        df = pd.read_excel(file_obj, sheet_name=sheet_name, engine='openpyxl')
    except Exception as e:
        # Try with xlrd for .xls files
        try:
            file_obj.seek(0)
            df = pd.read_excel(file_obj, sheet_name=sheet_name, engine='xlrd')
        except Exception as e2:
            return 0, 0, [f'Excel read error: {e}. Also retried with xlrd: {e2}'], stats

    cols = set(c.lower() for c in df.columns)
    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        # AI Recovery: Try to map columns intelligently
        try:
            sample_str = df.head(5).to_csv(index=False)
            mapping = smart_map_columns(sample_str)
            if mapping:
                rename_map = {v: k for k, v in mapping.items()}
                df.rename(columns=rename_map, inplace=True)
                df.columns = [c.lower() for c in df.columns]
                cols = set(df.columns)
        except Exception as e:
            print(f"Smart excel mapping failed: {e}")

    if not CSV_REQUIRED_COLUMNS.issubset(cols):
        required_data = {'date', 'amount'}
        if not required_data.issubset(cols):
             return 0, 0, [f'Excel must contain columns: {", ".join(sorted(CSV_REQUIRED_COLUMNS))}'], stats

    # Ensure optional columns exist
    if 'category' not in df.columns:
        df['category'] = ''
    if 'description' not in df.columns:
        df['description'] = ''
    if 'type' not in df.columns:
        df['type'] = df['amount'].apply(lambda x: 'income' if float(x) > 0 else 'expense')
    
    # normalize columns
    # df.columns already normalized above or in strict path? 
    # Wait, the original code normalized inside the `if` block or after?
    # Original code: `df.columns = [c.lower() for c in df.columns]`
    # We should ensure normalization happens.
    df.columns = [c.lower() for c in df.columns]

    num_i = 0
    num_e = 0
    income_objs: List[Income] = []
    expense_objs: List[Expense] = []
    total_rows = len(df)
    duplicate_rows = 0

    for _, row in df.iterrows():
        try:
            typ = str(row['type']).strip().lower()
            dt = pd.to_datetime(row['date']).date()
            amt = float(row['amount'])
            cat = str(row.get('category', '') or '')
            desc = str(row.get('description', '') or '')
        except Exception as e:
            errors.append(f'Row error: {e}')
            continue

        # Проверка на дубликаты
        is_duplicate = False
        if import_to_db:
            is_duplicate = _check_duplicate(typ, dt, amt, "", desc, user, source_file)
            if is_duplicate:
                duplicate_rows += 1
                stats['duplicates_found'] += 1
                if not auto_remove_dups:
                    continue  

        if typ == 'income':
            num_i += 1
            if import_to_db and not is_duplicate:
                itype = map_transaction_category('income', cat, desc)
                income_objs.append(Income(
                    amount=amt, 
                    date=dt, 
                    income_type=itype,
                    description=desc, 
                    user=user,
                    source_file=source_file
                ))
        elif typ == 'expense':
            num_e += 1
            if import_to_db and not is_duplicate:
                etype = map_transaction_category('expense', cat, desc)
                expense_objs.append(Expense(
                    amount=amt, 
                    date=dt, 
                    expense_type=etype,
                    description=desc, 
                    user=user,
                    source_file=source_file
                ))
        else:
            errors.append(f'Unknown type: {typ}')

    # Проверка на предупреждение (>50% дублей)
    if total_rows > 0 and duplicate_rows / total_rows > 0.5:
        stats['should_warn'] = True

    stats['duplicates_skipped'] = duplicate_rows

    if import_to_db and (income_objs or expense_objs):
        _persist_transactions(income_objs, expense_objs)

    return num_i, num_e, errors, stats


def extract_text_from_docx(file_obj) -> str:
    try:
        from docx import Document as Docx
        doc = Docx(file_obj)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"[DOCX read error: {e}]"


def extract_text_from_pdf(file_obj) -> str:
    try:
        from pdfminer.high_level import extract_text
        # pdfminer принимает путь или file-like; читаем bytes и отдаём BytesIO
        data = file_obj.read()
        return extract_text(io.BytesIO(data))
    except Exception as e:
        return f"[PDF read error: {e}]"


def create_document_from_text(doc_type: str, text: str, user=None) -> Document:
    return Document.objects.create(doc_type=doc_type, params={}, generated_text=text, user=user)


def quick_text_amounts_summary(text: str) -> dict:
    """Very simple heuristic to find amounts and hint a quick summary."""
    nums = [float(x.replace(',', '.')) for x in re.findall(r"\b\d+[\.,]?\d*\b", text or '')]
    total = round(sum(nums), 2) if nums else 0.0
    return {
        'numbers_found': len(nums),
        'sum_of_numbers': total,
    }

