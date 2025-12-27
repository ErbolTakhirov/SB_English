from datetime import date, timedelta
import io
import base64
import uuid
import json
from typing import Dict, List, Any
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from django.db.models import Sum, Q
from django.utils import timezone
from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from .models import (
    Income, Expense, Event, Document, Tag, ChatSession, ChatMessage, UploadedFile,
    UserProfile, UserGoal, TeenChatSession, TeenChatMessage,
    LearningModule, Quiz, QuizQuestion, UserQuizAttempt,
    Achievement, UserAchievement, FinancialInsight, ScamAlert, UserProgress
)
from .forms import IncomeForm, ExpenseForm, EventForm, DocumentForm, CustomUserCreationForm, CustomAuthenticationForm
from .ml.predictor import ExpenseAutoCategorizer
from .ml.forecast import forecast_next_month_profit
from .ml.recommender import build_recommendations
from .ml.document_generator import generate_document_text

# Teen-specific AI services
from .ai_services.teen_coach import teen_coach
from .ai_services.gamification import gamification_engine
from .ai_services.llm_manager import llm_manager


def logout_view(request):
    """
    Handle logout for both GET and POST requests.
    """
    logout(request)
    return redirect('core:login')

def get_demo_data():
    """
    Get demo data for hackathon presentation
    """
    return {
        'demo_user': {
            'name': 'Айжан',
            'age': 16,
            'monthly_allowance': 5000,
            'currency': 'KGS'
        },
        'demo_goals': [
            {
                'title': 'iPhone 15',
                'target_amount': 80000,
                'current_amount': 25000,
                'progress': 31,
                'target_date': '2025-06-01'
            },
            {
                'title': 'Курсы программирования',
                'target_amount': 15000,
                'current_amount': 8000,
                'progress': 53,
                'target_date': '2025-04-15'
            }
        ],
        'demo_achievements': [
            {'title': 'Первые шаги', 'icon': '🚀', 'category': 'milestone'},
            {'title': 'Накопитель', 'icon': '💰', 'category': 'saving'},
            {'title': 'Ученик', 'icon': '📚', 'category': 'learning'}
        ],
        'demo_insights': [
            {
                'title': 'Совет недели',
                'content': 'Ты тратишь 40% денег на развлечения. Попробуй снизить до 30%!'
            }
        ]
    }

@login_required
def teen_dashboard(request):
    """
    Main teen dashboard with modern, gamified interface
    """
    try:
        user = request.user
        
        # Ensure profile exists
        if not hasattr(user, 'teen_profile'):
            UserProfile.objects.get_or_create(user=user)
        profile = user.teen_profile
        
        # Ensure progress exists (crucial for gamification engine)
        if not hasattr(user, 'progress'):
            UserProgress.objects.get_or_create(user=user)
        
        # Get gamification data
        gamification_data = gamification_engine.get_user_dashboard_data(user)
        
        # Get recent goals
        recent_goals = user.goals.filter(status='active')[:3]
        
        # Get recent spending insights
        recent_insights = user.financial_insights.filter(is_read=False)[:3]
        
        # Get active learning modules
        learning_modules = LearningModule.objects.filter(
            is_published=True
        ).order_by('difficulty', 'created_at')[:4]
        
        # Calculate today's spending
        today = date.today()
        today_expenses = user.teen_expenses.filter(date=today).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Calculate this week's spending
        week_start = today - timedelta(days=today.weekday())
        week_expenses = user.teen_expenses.filter(
            date__gte=week_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get AI coach chat sessions
        recent_chats = user.teen_chat_sessions.order_by('-updated_at')[:2]
        
        # Demo mode data
        demo_data = get_demo_data() if profile.demo_mode else None
        
        context = {
            'user': user,
            'profile': profile,
            'gamification': gamification_data,
            'recent_goals': recent_goals,
            'recent_insights': recent_insights,
            'learning_modules': learning_modules,
            'today_expenses': float(today_expenses),
            'week_expenses': float(week_expenses),
            'recent_chats': recent_chats,
            'demo_data': demo_data,
            'current_date': today,
        }
        
        return render(request, 'teen/dashboard.html', context)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in teen dashboard: {e}")
        messages.error(request, f"Ошибка загрузки подросткового раздела: {e}")
        return redirect('core:dashboard')  # Редирект на основной дашборд с графиками

from .utils.file_ingest import (
    import_csv_transactions,
    import_excel_transactions,
    extract_text_from_docx,
    extract_text_from_pdf,
    create_document_from_text,
    quick_text_amounts_summary,
    find_duplicates,
)
from .utils.export import export_chat_to_csv, export_chat_to_docx, export_chat_to_pdf
from .llm import get_ai_advice_from_data, chat_with_context, _compute_content_hash
from .utils.analytics import (
    update_user_financial_memory,
    get_user_financial_memory,
    parse_actionable_items,
    detect_anomalies_automatically,
)
from django.views.decorators.csrf import csrf_exempt

# 🚀 NEW: Импорты для WOW-features
from core.ai.views import ai_chat_api_v2
from core.ai.wow_features import (
    ai_chat_streaming,
    ai_confidence_score,
    financial_health_score,
    ai_explain_reasoning,
)


def _render_plot_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ==========================
# MONTHLY SUMMARY (GLOBAL MEMORY TABLE)
# ==========================
def _month_key(dt: date) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _compute_monthly_summary(user) -> dict:
    """Агрегирует все транзакции пользователя по месяцам с топ-3 категориями.
    Возвращает структуру:
    {
      'months': {
         'YYYY-MM': {
             'income_total': float,
             'expense_total': float,
             'tx_count': int,
             'top_income_cats': [cat...],
             'top_expense_cats': [cat...],
         }, ...
      },
      'ordered_keys': [ ... sorted months ... ]
    }
    """
    months: Dict[str, dict] = {}
    # Инициализация из доходов
    for inc in Income.objects.filter(user=user):
        mk = _month_key(inc.date)
        m = months.setdefault(mk, {
            'income_total': 0.0,
            'expense_total': 0.0,
            'tx_count': 0,
            'income_by_cat': {},
            'expense_by_cat': {},
        })
        m['income_total'] += float(inc.amount)
        m['tx_count'] += 1
        cat = getattr(inc, 'income_type', 'other')
        m['income_by_cat'][cat] = m['income_by_cat'].get(cat, 0.0) + float(inc.amount)
    # Из расходов
    for exp in Expense.objects.filter(user=user):
        mk = _month_key(exp.date)
        m = months.setdefault(mk, {
            'income_total': 0.0,
            'expense_total': 0.0,
            'tx_count': 0,
            'income_by_cat': {},
            'expense_by_cat': {},
        })
        m['expense_total'] += float(exp.amount)
        m['tx_count'] += 1
        cat = getattr(exp, 'expense_type', 'other')
        m['expense_by_cat'][cat] = m['expense_by_cat'].get(cat, 0.0) + float(exp.amount)

    # Топ категории и очистка
    for mk, m in months.items():
        top_inc = sorted(m['income_by_cat'].items(), key=lambda x: x[1], reverse=True)[:3]
        top_exp = sorted(m['expense_by_cat'].items(), key=lambda x: x[1], reverse=True)[:3]
        m['top_income_cats'] = [k for k, _ in top_inc]
        m['top_expense_cats'] = [k for k, _ in top_exp]
        # удалить подробности
        del m['income_by_cat']
        del m['expense_by_cat']

    ordered = sorted(months.keys())
    return { 'months': months, 'ordered_keys': ordered }


def _build_monthly_table_md(summary: dict) -> str:
    """Строит markdown-таблицу по месячной сводке."""
    header = (
        "| Month | Income | Expenses | Top Income | Top Expenses | Transactions |\n"
        "|---|---|---|---|---|---|"
    )
    lines = [header]
    for mk in summary.get('ordered_keys', []):
        m = summary['months'][mk]
        ym = mk.split('-')
        month_h = f"{ym[1]}.{ym[0]}"
        top_i = ", ".join(m.get('top_income_cats', []) or []) or "—"
        top_e = ", ".join(m.get('top_expense_cats', []) or []) or "—"
        lines.append(
            f"| {month_h} | {round(m['income_total'], 2)} | {round(m['expense_total'], 2)} | {top_i} | {top_e} | {m['tx_count']} |"
        )
    return "\n".join(lines)


@login_required
def workspace(request):
    """
    Главный AI workspace интерфейс - чатбот с поддержкой загрузки файлов,
    графиков и markdown ответов.
    """
    return render(request, 'workspace.html', {
        'user': request.user
    })


@login_required
def ai_demo(request):
    """
    🚀 Демо-страница WOW-features для хакатона.
    Показывает все новые AI возможности.
    """
    return render(request, 'ai_demo.html', {
        'user': request.user
    })


@login_required
def dashboard(request):
    # Upload handler
    if request.method == 'POST' and request.FILES.get('upload_file'):
        f = request.FILES['upload_file']
        import_to_db = request.POST.get('import_to_db') == 'on'
        name = (f.name or '').lower()
        try:
            # Создаем UploadedFile для source_file
            from django.core.files.base import ContentFile
            file_content = f.read()
            file_for_db = ContentFile(file_content, name=f.name)
            file_obj = UploadedFile.objects.create(
                user=request.user,
                file=file_for_db,
                original_name=f.name,
                file_type=name.split('.')[-1] if '.' in name else 'unknown',
                file_size=len(file_content),
                processed=False,
                metadata={},
            )
            
            import io
            file_for_processing = io.BytesIO(file_content)
            
            if name.endswith('.csv'):
                num_i, num_e, errs, stats = import_csv_transactions(
                    file_for_processing, 
                    import_to_db=import_to_db, 
                    user=request.user,
                    source_file=file_obj
                )
                file_obj.metadata = {"imported": {"incomes": num_i, "expenses": num_e}, "import_stats": stats}
                file_obj.processed = True
                file_obj.save()
                if num_i or num_e:
                    messages.success(request, f'Imported: income {num_i}, expenses {num_e}.')
                if stats.get('duplicates_skipped', 0) > 0:
                    messages.info(request, f'Skipped duplicates: {stats["duplicates_skipped"]}.')
                if stats.get('should_warn', False):
                    messages.warning(request, f'Detected >50% duplicates. Recommended to check file.')
                for e in errs:
                    messages.warning(request, e)
            elif name.endswith('.xlsx') or name.endswith('.xls'):
                num_i, num_e, errs, stats = import_excel_transactions(
                    file_for_processing, 
                    import_to_db=import_to_db, 
                    user=request.user,
                    source_file=file_obj
                )
                file_obj.metadata = {"imported": {"incomes": num_i, "expenses": num_e}, "import_stats": stats}
                file_obj.processed = True
                file_obj.save()
                if num_i or num_e:
                    messages.success(request, f'Imported: income {num_i}, expenses {num_e}.')
                if stats.get('duplicates_skipped', 0) > 0:
                    messages.info(request, f'Skipped duplicates: {stats["duplicates_skipped"]}.')
                if stats.get('should_warn', False):
                    messages.warning(request, f'Detected >50% duplicates. Recommended to check file.')
                for e in errs:
                    messages.warning(request, e)
            elif name.endswith('.docx'):
                text = extract_text_from_docx(f)
                doc = create_document_from_text('contract', text, user=request.user)
                s = quick_text_amounts_summary(text)
                messages.success(request, f'DOCX uploaded as document #{doc.id}. Found numbers: {s["numbers_found"]}, sum: {s["sum_of_numbers"]}.')
            elif name.endswith('.pdf'):
                text = extract_text_from_pdf(f)
                doc = create_document_from_text('contract', text, user=request.user)
                s = quick_text_amounts_summary(text)
                messages.success(request, f'PDF uploaded as document #{doc.id}. Found numbers: {s["numbers_found"]}, sum: {s["sum_of_numbers"]}.')
            else:
                messages.error(request, 'Only CSV, Excel (.xlsx, .xls), DOCX, PDF files are supported.')
        except Exception as ex:
            messages.error(request, f'File processing error: {ex}')

    # Filters
    start = request.GET.get('start')
    end = request.GET.get('end')

    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)
    if start:
        incomes = incomes.filter(date__gte=start)
        expenses = expenses.filter(date__gte=start)
    if end:
        incomes = incomes.filter(date__lte=end)
        expenses = expenses.filter(date__lte=end)

    income_total = incomes.aggregate(total=Sum('amount'))['total'] or 0
    expense_total = expenses.aggregate(total=Sum('amount'))['total'] or 0
    profit = income_total - expense_total

    context = {
        'income_total': income_total,
        'expense_total': expense_total,
        'profit': profit,
        'start': start,
        'end': end,
    }
    return render(request, 'dashboard.html', context)


def records_api(request):
    """Unified records feed with filters and simple pagination."""
    types = request.GET.getlist('type') or ['income', 'expense', 'document', 'event']
    start = request.GET.get('start')
    end = request.GET.get('end')
    search = (request.GET.get('search') or '').strip().lower()
    tag_names = request.GET.getlist('tag')
    page = int(request.GET.get('page', '1'))
    page_size = min(100, int(request.GET.get('page_size', '25')))

    items = []

    def add_items(qs, type_name, fields):
        nonlocal items
        if start:
            qs = qs.filter(date__gte=start) if hasattr(qs.model, 'date') else qs
        if end:
            qs = qs.filter(date__lte=end) if hasattr(qs.model, 'date') else qs
        if tag_names and hasattr(qs.model, 'tags'):
            qs = qs.filter(tags__name__in=tag_names).distinct()
        for obj in qs[:1000]:
            data = {'id': obj.id, 'type': type_name}
            for name in fields:
                val = getattr(obj, name, None)
                if name in ['income_type', 'expense_type']:
                    data['category'] = val
                else:
                    data[name] = val
            # simple text search across description/title/params
            blob = ' '.join(str(v) for v in data.values()).lower()
            if search and search not in blob:
                continue
            # tags
            if hasattr(obj, 'tags'):
                data['tags'] = list(obj.tags.values_list('name', flat=True))
            items.append(data)

    # Фильтруем только данные текущего пользователя
    if 'income' in types:
        add_items(Income.objects.filter(user=request.user).order_by('-date', '-id'), 'income', ['amount', 'date', 'income_type', 'description'])
    if 'expense' in types:
        add_items(Expense.objects.filter(user=request.user).order_by('-date', '-id'), 'expense', ['amount', 'date', 'expense_type', 'description'])
    if 'event' in types:
        add_items(Event.objects.filter(user=request.user).order_by('-date', '-id'), 'event', ['date', 'title', 'description'])
    if 'document' in types:
        add_items(Document.objects.filter(user=request.user).order_by('-created_at', '-id'), 'document', ['doc_type', 'created_at'])

    # sort mixed items by date/created_at desc
    def sort_key(x):
        return x.get('date') or x.get('created_at') or ''
    items.sort(key=sort_key, reverse=True)

    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return JsonResponse({'total': total, 'page': page, 'page_size': page_size, 'items': items[start_idx:end_idx]})


@login_required
def dashboard_data_api(request):
    """API для получения детализированных данных для интерактивных графиков дашборда."""
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    start = request.GET.get('start')
    end = request.GET.get('end')
    category = request.GET.get('category')  # Фильтр по категории
    group_by = request.GET.get('group_by', 'day')  # day, week, month

    incomes = Income.objects.filter(user=request.user).order_by('date')
    expenses = Expense.objects.filter(user=request.user).order_by('date')
    
    if start:
        incomes = incomes.filter(date__gte=start)
        expenses = expenses.filter(date__gte=start)
    if end:
        incomes = incomes.filter(date__lte=end)
        expenses = expenses.filter(date__lte=end)
    if category:
        incomes = incomes.filter(income_type=category)
        expenses = expenses.filter(expense_type=category)

    # Данные по дням для time series
    daily_data = defaultdict(lambda: {'income': 0.0, 'expense': 0.0, 'income_count': 0, 'expense_count': 0, 'top_category_income': None, 'top_category_expense': None})
    daily_categories = defaultdict(lambda: {'income': defaultdict(float), 'expense': defaultdict(float)})
    
    # Собираем все уникальные даты
    all_dates = set()
    
    for inc in incomes:
        date_key = inc.date.isoformat()
        all_dates.add(date_key)
        daily_data[date_key]['income'] += float(inc.amount)
        daily_data[date_key]['income_count'] += 1
        daily_categories[date_key]['income'][inc.income_type] += float(inc.amount)
    
    for exp in expenses:
        date_key = exp.date.isoformat()
        all_dates.add(date_key)
        daily_data[date_key]['expense'] += float(exp.amount)
        daily_data[date_key]['expense_count'] += 1
        daily_categories[date_key]['expense'][exp.expense_type] += float(exp.amount)
    
    # Определяем топ категорию для каждого дня
    for date_key in daily_data:
        if daily_categories[date_key]['income']:
            daily_data[date_key]['top_category_income'] = max(daily_categories[date_key]['income'].items(), key=lambda x: x[1])[0]
        if daily_categories[date_key]['expense']:
            daily_data[date_key]['top_category_expense'] = max(daily_categories[date_key]['expense'].items(), key=lambda x: x[1])[0]
    
    # Сортируем по дате и заполняем пропуски (для визуализации разрывов)
    from datetime import timedelta
    sorted_dates = sorted(all_dates)
    
    # Если нужно заполнить пропуски - создаем список всех дней между первой и последней датой
    # ВАЖНО: заполняем только если период не очень большой (до 90 дней), иначе график будет перегружен
    if sorted_dates and group_by == 'day':
        first_date = datetime.fromisoformat(sorted_dates[0]).date()
        last_date = datetime.fromisoformat(sorted_dates[-1]).date()
        days_diff = (last_date - first_date).days
        
        # Заполняем пропуски только если период <= 90 дней (иначе слишком много точек)
        if days_diff <= 90:
            current_date = first_date
            complete_dates = []
            while current_date <= last_date:
                date_key = current_date.isoformat()
                complete_dates.append(date_key)
                # Инициализируем день, если его нет
                if date_key not in daily_data:
                    daily_data[date_key] = {'income': 0.0, 'expense': 0.0, 'income_count': 0, 'expense_count': 0, 'top_category_income': None, 'top_category_expense': None}
                current_date += timedelta(days=1)
            sorted_dates = complete_dates
        else:
            # Для больших периодов не заполняем пропуски - оставляем только дни с данными
            sorted_dates = sorted(daily_data.keys())
    else:
        sorted_dates = sorted(daily_data.keys())
    
    # Формируем данные для графиков
    dates = []
    income_values = []
    expense_values = []
    profit_values = []
    cumulative_income = []
    cumulative_profit = []
    cum_income = 0
    cum_profit = 0
    
    # Moving average (7 дней)
    moving_avg_window = 7
    income_ma = []
    expense_ma = []
    
    # Данные для tooltips
    tooltips_income = []
    tooltips_expense = []
    
    for date_key in sorted_dates:
        data = daily_data[date_key]
        dates.append(date_key)
        income_val = data['income']
        expense_val = data['expense']
        profit_val = income_val - expense_val
        
        income_values.append(round(income_val, 2))
        expense_values.append(round(expense_val, 2))
        profit_values.append(round(profit_val, 2))
        
        cum_income += income_val
        cum_profit += profit_val
        cumulative_income.append(round(cum_income, 2))
        cumulative_profit.append(round(cum_profit, 2))
        
        # Tooltips (HTML формат для Plotly)
        tooltip_income = f"<b>💰 Income</b><br>Date: {date_key}<br>Amount: {income_val:,.2f} RUB<br>Transactions: {data['income_count']}"
        if data['top_category_income']:
            tooltip_income += f"<br>📂 Top Category: {data['top_category_income']}"
        tooltips_income.append(tooltip_income)
        
        tooltip_expense = f"<b>💸 Expenses</b><br>Date: {date_key}<br>Amount: {expense_val:,.2f} RUB<br>Transactions: {data['expense_count']}"
        if data['top_category_expense']:
            tooltip_expense += f"<br>📂 Top Category: {data['top_category_expense']}"
        tooltips_expense.append(tooltip_expense)
        
        # Moving average
        if len(income_values) >= moving_avg_window:
            income_ma.append(round(sum(income_values[-moving_avg_window:]) / moving_avg_window, 2))
            expense_ma.append(round(sum(expense_values[-moving_avg_window:]) / moving_avg_window, 2))
        else:
            income_ma.append(None)
            expense_ma.append(None)
    
    # Данные по категориям (для pie/bar charts)
    # Using 'expense_type' alias as 'category'
    exp_by_cat = expenses.values('expense_type').annotate(total=Sum('amount')).order_by('-total')
    # Transform keys to match expected frontend 'category'
    exp_by_cat = [{'category': x['expense_type'], 'total': x['total']} for x in exp_by_cat]

    inc_by_cat = incomes.values('income_type').annotate(total=Sum('amount')).order_by('-total')
    inc_by_cat = [{'category': x['income_type'], 'total': x['total']} for x in inc_by_cat]
    
    # Аномалии и события - фильтруем по периоду
    anomalies = detect_anomalies_automatically(request.user)
    events_data = []
    for anomaly in anomalies[:15]:  # Топ-15 аномалий
        # Проверяем, попадает ли аномалия в выбранный период
        anomaly_date_str = anomaly.get('date') or anomaly.get('month', '')
        if not anomaly_date_str:
            continue
            
        # Если указан месяц в формате YYYY-MM, берем первый день месяца
        if len(anomaly_date_str) == 7 and '-' in anomaly_date_str:  # Формат YYYY-MM
            anomaly_date_str = f"{anomaly_date_str}-01"
        
        try:
            # Парсим дату
            if len(anomaly_date_str) == 10:  # YYYY-MM-DD
                anomaly_date = datetime.fromisoformat(anomaly_date_str).date()
            else:
                # Пытаемся распарсить другими способами
                try:
                    anomaly_date = datetime.strptime(anomaly_date_str, '%Y-%m-%d').date()
                except:
                    continue
            
            # Фильтруем по периоду
            if start:
                start_date = datetime.fromisoformat(start).date() if isinstance(start, str) and len(start) == 10 else start
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date).date()
                    except:
                        pass
                if isinstance(anomaly_date, type(start_date)) and anomaly_date < start_date:
                    continue
                    
            if end:
                end_date = datetime.fromisoformat(end).date() if isinstance(end, str) and len(end) == 10 else end
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.fromisoformat(end_date).date()
                    except:
                        pass
                if isinstance(anomaly_date, type(end_date)) and anomaly_date > end_date:
                    continue
        except Exception as e:
            # Если не удалось распарсить дату, пропускаем
            continue
        
        events_data.append({
            'date': anomaly_date.isoformat() if hasattr(anomaly_date, 'isoformat') else anomaly_date_str,
            'type': anomaly.get('type', 'anomaly'),
            'message': anomaly.get('message', ''),
            'amount': anomaly.get('amount', anomaly.get('value', 0)),
            'severity': anomaly.get('severity', 'medium'),
        })
    
    # Данные по неделям (если группировка = week)
    weekly_data = {}
    monthly_data = {}
    
    if group_by == 'week' or group_by == 'month':
        from datetime import datetime as dt
        for date_key in sorted_dates:
            dt_obj = dt.fromisoformat(date_key)
            if group_by == 'week':
                week_key = dt_obj.strftime('%Y-W%W')
                if week_key not in weekly_data:
                    weekly_data[week_key] = {'income': 0, 'expense': 0, 'dates': []}
                weekly_data[week_key]['income'] += daily_data[date_key]['income']
                weekly_data[week_key]['expense'] += daily_data[date_key]['expense']
                weekly_data[week_key]['dates'].append(date_key)
            elif group_by == 'month':
                month_key = dt_obj.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'income': 0, 'expense': 0, 'dates': []}
                monthly_data[month_key]['income'] += daily_data[date_key]['income']
                monthly_data[month_key]['expense'] += daily_data[date_key]['expense']
                monthly_data[month_key]['dates'].append(date_key)
    
    return JsonResponse({
        'ok': True,
        'daily': {
            'dates': dates,
            'income': income_values,
            'expense': expense_values,
            'profit': profit_values,
            'cumulative_income': cumulative_income,
            'cumulative_profit': cumulative_profit,
            'moving_avg_income': income_ma,
            'moving_avg_expense': expense_ma,
            'tooltips_income': tooltips_income,
            'tooltips_expense': tooltips_expense,
        },
        'weekly': weekly_data if group_by == 'week' else {},
        'monthly': monthly_data if group_by == 'month' else {},
        'categories': {
            'expenses': [{'category': r['category'], 'total': round(float(r['total'] or 0), 2)} for r in exp_by_cat],
            'incomes': [{'category': r['category'], 'total': round(float(r['total'] or 0), 2)} for r in inc_by_cat],
        },
        'events': events_data,
        'group_by': group_by,
    })


@login_required
def ai_insights_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    group_by = request.GET.get('group_by', 'month')  # reserved for future

    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)
    if start:
        incomes = incomes.filter(date__gte=start)
        expenses = expenses.filter(date__gte=start)
    if end:
        incomes = incomes.filter(date__lte=end)
        expenses = expenses.filter(date__lte=end)

    # KPIs
    from django.db.models import Sum
    income_total = float(incomes.aggregate(total=Sum('amount'))['total'] or 0.0)
    expense_total = float(expenses.aggregate(total=Sum('amount'))['total'] or 0.0)
    profit = income_total - expense_total

    # Simple forecast (next month profit)
    next_profit_data = forecast_next_month_profit(incomes, expenses, user=request.user)

    # Recommendations
    recommendations = build_recommendations(incomes, expenses)

    # Alerts: expense categories above rolling average
    alerts = []
    exp_by_cat = expenses.values('expense_type').annotate(total=Sum('amount')).order_by('-total')
    avg_expense = (expense_total / max(1, exp_by_cat.count())) if exp_by_cat else 0
    for row in exp_by_cat:
        cat_name = row['expense_type']
        cat_total = float(row['total'] or 0)
        if avg_expense and cat_total > avg_expense * 1.5:
            alerts.append({
                'type': 'expense_spike',
                'message': f"Expenses in category '{cat_name}' are above average",
                'severity': 'warning',
                'category': cat_name,
                'value': cat_total,
            })

    # Category breakdown for charts
    cat_breakdown = [
        {'category': r['expense_type'], 'total': float(r['total'] or 0)} for r in exp_by_cat
    ]

    return JsonResponse({
        'kpis': {
            'income_total': round(income_total, 2),
            'expense_total': round(expense_total, 2),
            'profit': round(profit, 2),
        },
        'forecast': next_profit_data,
        'recommendations': recommendations,
        'alerts': alerts,
        'breakdowns': {
            'expense_by_category': cat_breakdown,
        },
        'group_by': group_by,
    })


def _serialize_transactions_csv(incomes_qs, expenses_qs) -> str:
    lines = ["type,date,amount,category,description"]
    for o in incomes_qs:
        desc = (o.description or '').replace('\n', ' ').replace(',', ' ')
        # Use income_type instead of category
        cat = getattr(o, 'income_type', 'other')
        lines.append(f"income,{o.date},{float(o.amount)},{cat},{desc}")
    for o in expenses_qs:
        desc = (o.description or '').replace('\n', ' ').replace(',', ' ')
        # Use expense_type instead of category
        cat = getattr(o, 'expense_type', 'other')
        lines.append(f"expense,{o.date},{float(o.amount)},{cat},{desc}")
    return "\n".join(lines)


@csrf_exempt
@login_required
def upload_api(request):
    """AJAX upload endpoint: parse file, optionally import to DB, return summary + AI advice."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    # Проверка аутентификации
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Требуется авторизация'}, status=401)
    
    f = request.FILES.get('upload_file')
    import_to_db = (request.POST.get('import_to_db') or 'on') == 'on'
    session_id = request.POST.get('session_id') or None
    if not f:
        return JsonResponse({'ok': False, 'error': 'Файл не передан'}, status=400)
    name = (f.name or '').lower()
    
    # Сохраняем содержимое файла в память для повторного использования
    file_content = None
    file_size = getattr(f, 'size', 0)
    try:
        file_content = f.read()
        # Создаем новый файловый объект из содержимого для сохранения в БД
        from django.core.files.uploadedfile import InMemoryUploadedFile
        from django.core.files.base import ContentFile
        file_for_db = ContentFile(file_content, name=f.name)
    except Exception as e:
        import traceback
        print(f"Ошибка чтения файла: {e}")
        print(traceback.format_exc())
        return JsonResponse({'ok': False, 'error': f'Ошибка чтения файла: {str(e)}'}, status=500)
    
    try:
        summary = {}
        imported = {"incomes": 0, "expenses": 0}
        import_stats = {}
        
        # Сначала создаем UploadedFile, чтобы иметь file_obj для source_file
        file_obj = UploadedFile.objects.create(
            user=request.user,
            file=file_for_db,
            original_name=f.name,
            file_type=name.split('.')[-1] if '.' in name else 'unknown',
            file_size=file_size or len(file_content),
            processed=False,  # Будет установлено в True после успешной обработки
            metadata={},
        )
        
        # Используем BytesIO для обработки файла
        import io
        file_for_processing = io.BytesIO(file_content)
        
        if name.endswith('.csv'):
            num_i, num_e, errs, stats = import_csv_transactions(
                file_for_processing, 
                import_to_db=import_to_db, 
                user=request.user,
                source_file=file_obj
            )
            summary['errors'] = errs
            imported = {"incomes": num_i, "expenses": num_e}
            import_stats = stats
        elif name.endswith('.xlsx') or name.endswith('.xls'):
            num_i, num_e, errs, stats = import_excel_transactions(
                file_for_processing, 
                import_to_db=import_to_db, 
                user=request.user,
                source_file=file_obj
            )
            summary['errors'] = errs
            imported = {"incomes": num_i, "expenses": num_e}
            import_stats = stats
        elif name.endswith('.docx'):
            file_for_processing.seek(0)
            text = extract_text_from_docx(file_for_processing)
            doc = create_document_from_text('contract', text, user=request.user)
            s = quick_text_amounts_summary(text)
            summary = {"document_id": doc.id, **s}
        elif name.endswith('.pdf'):
            file_for_processing.seek(0)
            text = extract_text_from_pdf(file_for_processing)
            doc = create_document_from_text('contract', text, user=request.user)
            s = quick_text_amounts_summary(text)
            summary = {"document_id": doc.id, **s}
        else:
            file_obj.delete()  # Удаляем файл, если формат не поддерживается
            return JsonResponse({'ok': False, 'error': 'Поддерживаются файлы CSV, Excel (.xlsx, .xls), DOCX, PDF'}, status=400)

        # Обновляем метаданные файла
        file_obj.metadata = {"imported": imported, "summary": summary, "import_stats": import_stats}
        file_obj.processed = True
        file_obj.save()

        # Attach to session if provided
        attached_session_id = None
        if session_id:
            try:
                sess = ChatSession.objects.get(session_id=session_id, user=request.user)
                sess.files.add(file_obj)
                # Update data_summaries with brief summary under file id
                ds = dict(sess.data_summaries or {})
                ds[str(file_obj.id)] = {
                    "original_name": file_obj.original_name,
                    "file_type": file_obj.file_type,
                    "imported": imported,
                    "summary": summary,
                    "uploaded_at": file_obj.uploaded_at.isoformat(),
                }
                sess.data_summaries = ds
                sess.save()
                attached_session_id = sess.session_id
            except ChatSession.DoesNotExist:
                attached_session_id = None

        # Reuse KPIs calculation
        from django.db.models import Sum
        from django.utils import timezone
        
        # Build latest metrics for charts and AI
        start = request.GET.get('start')
        end = request.GET.get('end')
        incomes = Income.objects.filter(user=request.user)
        expenses = Expense.objects.filter(user=request.user)
        if start:
            incomes = incomes.filter(date__gte=start)
            expenses = expenses.filter(date__gte=start)
        if end:
            incomes = incomes.filter(date__lte=end)
            expenses = expenses.filter(date__lte=end)
        data_blob = _serialize_transactions_csv(incomes, expenses)

        income_total = float(incomes.aggregate(total=Sum('amount'))['total'] or 0.0)
        expense_total = float(expenses.aggregate(total=Sum('amount'))['total'] or 0.0)
        profit = income_total - expense_total

        # КРИТИЧНО: После загрузки ВСЕГДА обновляем финансовую память (summary по всем месяцам)
        memory = None
        anomaly_alerts = []
        try:
            memory = update_user_financial_memory(request.user, force_refresh=True)
            anomaly_alerts = detect_anomalies_automatically(request.user)
            
            # Сохраняем в сессию, если есть
            if attached_session_id:
                try:
                    sess = ChatSession.objects.get(session_id=attached_session_id, user=request.user)
                    analytics = dict(sess.analytics_summaries or {})
                    analytics['monthly_summary'] = memory
                    analytics['last_update'] = timezone.now().isoformat()
                    sess.analytics_summaries = analytics
                    sess.save()
                except ChatSession.DoesNotExist:
                    pass
        except Exception as e:
            import traceback
            print(f"Ошибка обновления памяти: {e}")
            print(traceback.format_exc())

        # Генерируем AI-совет с учетом всей финансовой памяти
        ai_text = ""
        try:
            ai_text = get_ai_advice_from_data(
                data_blob,
                extra_instruction="Проанализируй загруженные данные и дай краткую сводку с рекомендациями. Используй все данные из таблицы.",
                user=request.user  # Передаем user для получения таблиц
            )
        except Exception as e:
            import traceback
            print(f"Ошибка генерации AI совета: {e}")
            print(traceback.format_exc())
            # Fallback без user
            try:
                ai_text = get_ai_advice_from_data(data_blob)
            except Exception:
                ai_text = "Данные загружены успешно. Ошибка при генерации AI-совета."

        return JsonResponse({
            'ok': True,
            'imported': imported,
            'summary': summary,
            'kpis': {
                'income_total': round(income_total, 2),
                'expense_total': round(expense_total, 2),
                'profit': round(profit, 2),
            },
            'ai_advice': ai_text,
            'anomaly_alerts': anomaly_alerts[:5] if anomaly_alerts else [],  # Топ-5 аномалий
            'file': {
                'id': file_obj.id,
                'original_name': file_obj.original_name,
                'file_type': file_obj.file_type,
                'file_size': file_obj.file_size,
                'uploaded_at': file_obj.uploaded_at.isoformat(),
            },
            'attached_to_session': attached_session_id,
            'memory_updated': True,  # Флаг, что память обновлена
        })
    except Exception as ex:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = str(ex)
        print(f"Ошибка в upload_api: {error_msg}")
        print(error_trace)
        # В режиме DEBUG возвращаем детали ошибки
        response_data = {
            'ok': False,
            'error': f'Ошибка обработки файла: {error_msg}'
        }
        if settings.DEBUG:
            response_data['traceback'] = error_trace
        return JsonResponse(response_data, status=500)


@csrf_exempt
@login_required
def ai_chat_api(request):
    """
    Chat API с поддержкой истории диалога и проверкой на повторения.
    Принимает: message, session_id (опционально), start, end (фильтры дат)
    Возвращает: reply (markdown), session_id, history
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    # Поддержка JSON запросов
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            msg = data.get('message', '').strip()
            session_id = data.get('session_id')
            start = data.get('start')
            end = data.get('end')
        else:
            msg = request.POST.get('message', '').strip()
            session_id = request.POST.get('session_id')
            start = request.POST.get('start')
            end = request.POST.get('end')
    except:
        msg = request.POST.get('message', '').strip()
        session_id = request.POST.get('session_id')
        start = request.POST.get('start')
        end = request.POST.get('end')
    
    if not msg:
        return JsonResponse({'ok': False, 'error': 'Пустое сообщение'}, status=400)
    
    # Ограничение длины сообщения
    if len(msg) > 5000:
        return JsonResponse({'ok': False, 'error': 'Сообщение слишком длинное (максимум 5000 символов)'}, status=400)
    
    # Настройки приватности из сессии/профиля
    use_local = False
    anonymize = True
    try:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.local_mode_only:
            use_local = True
        # Сессионные предпочтения пользователя
        use_local = request.session.get('use_local_llm', use_local)
        anonymize = request.session.get('anonymize_enabled', True)
    except Exception:
        pass

    # Переопределение через запрос
    try:
        if request.content_type == 'application/json':
            data_override = json.loads(request.body)
        else:
            data_override = request.POST
        if data_override is not None:
            if 'use_local' in data_override:
                use_local = bool(data_override.get('use_local'))
            if 'anonymize' in data_override:
                anonymize = bool(data_override.get('anonymize'))
    except Exception:
        pass

    # Получаем или создаем сессию с привязкой к пользователю
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(session_id=session_id, user=request.user)
    else:
        session_id = str(uuid.uuid4())
        session = ChatSession.objects.create(session_id=session_id, user=request.user)
    
    # Автоматически генерируем название сессии из первого сообщения, если оно пустое
    if not session.title:
        session.title = msg[:50] + ('...' if len(msg) > 50 else '')
        session.save()
    
    # Сохраняем сообщение пользователя
    user_msg = ChatMessage.objects.create(
        session=session,
        role='user',
        content=msg,
        content_hash=_compute_content_hash(msg)
    )
    
    # КРИТИЧНО: Встраиваем mini-memory: сводки загруженных файлов для данной сессии
    try:
        session_memory = []
        if getattr(session, 'data_summaries', None):
            for k, v in (session.data_summaries or {}).items():
                try:
                    oname = v.get('original_name')
                    ftype = v.get('file_type')
                    imp = v.get('imported', {})
                    summ = v.get('summary', {})
                    session_memory.append(f"FILE[{k}]: {oname} ({ftype}); imported incomes={imp.get('incomes',0)}, expenses={imp.get('expenses',0)}; summary={json.dumps(summ, ensure_ascii=False)}")
                except Exception:
                    continue
        session_memory_block = "\n\n# SESSION_MEMORY\n" + "\n".join(session_memory) if session_memory else ""
    except Exception:
        session_memory_block = ""
    
    # Получаем историю диалога для контекста
    history_messages = []
    for prev_msg in ChatMessage.objects.filter(session=session).exclude(id=user_msg.id).order_by('created_at'):
        history_messages.append({
            'role': prev_msg.role,
            'content': prev_msg.content
        })
    
    # Добавляем текущее сообщение
    history_messages.append({'role': 'user', 'content': msg})
    
    # 🚀 NEW: Используем улучшенную систему с query analyzer + context builder
    try:
        from core.ai.advisor import get_financial_advice
        from core.ai.query_analyzer import analyze_query
        
        # Анализируем запрос
        query_analysis = analyze_query(msg)
        query_type = query_analysis.get('query_type', 'general')
        
        # Получаем улучшенный ответ
        ai_result = get_financial_advice(
            user=request.user,
            query=msg,
            session=session,
            use_local=use_local,
            anonymize=anonymize
        )
        
        reply = ai_result['response']
        context_used = ai_result.get('context_used', {})
        
    except Exception as e:
        # Fallback на старую систему если что-то пошло не так
        print(f"Ошибка в новой AI системе: {e}, использую fallback")
        reply = chat_with_context(
            history_messages,
            user_data=session_memory_block,
            session=session,
            check_duplicates=True,
            anonymize=anonymize,
            use_local=use_local,
            user=request.user
        )
        query_type = 'general'
        context_used = {}
    
    # 🎯 NEW: Рассчитываем confidence score
    confidence_data = None
    try:
        from core.ai.wow_features import ai_confidence_score as calc_confidence
        from django.test import RequestFactory
        
        # Создаем mock request для расчета confidence
        factory = RequestFactory()
        mock_request = factory.post('/api/ai/confidence/', 
                                   data=json.dumps({'message': msg}),
                                   content_type='application/json')
        mock_request.user = request.user
        
        confidence_response = calc_confidence(mock_request)
        confidence_data = json.loads(confidence_response.content)
    except Exception as e:
        print(f"Ошибка расчета confidence: {e}")
        confidence_data = {
            'confidence': 75,
            'level': 'medium',
            'icon': '🟡',
            'message': 'Средняя уверенность'
        }
    
    # 🏆 NEW: Рассчитываем health score (только если релевантно)
    health_score_data = None
    if query_type in ['advice', 'general', 'trends']:
        try:
            from core.ai.wow_features import financial_health_score as calc_health
            
            mock_request = factory.post('/api/ai/health-score/',
                                       data=json.dumps({}),
                                       content_type='application/json')
            mock_request.user = request.user
            
            health_response = calc_health(mock_request)
            health_score_data = json.loads(health_response.content)
        except Exception as e:
            print(f"Ошибка расчета health score: {e}")
    
    # Извлекаем actionable советы из ответа с поддержкой новых тегов
    actionable_items = parse_actionable_items(reply)
    
    # Сохраняем ответ ассистента
    assistant_msg = ChatMessage.objects.create(
        session=session,
        role='assistant',
        content=reply,
        content_hash=_compute_content_hash(reply),
        metadata={
            'actionable_items': actionable_items,
            'items_count': len(actionable_items),
        }
    )
    
    # Обновляем action_log в сессии
    try:
        action_log = dict(session.action_log or {})
        if 'advices_given' not in action_log:
            action_log['advices_given'] = 0
        if 'advices_completed' not in action_log:
            action_log['advices_completed'] = 0
        action_log['advices_given'] += len(actionable_items)
        action_log['last_advice_at'] = timezone.now().isoformat()
        action_log['total_messages'] = action_log.get('total_messages', 0) + 1
        
        # Сохраняем список всех советов (только активные, выполненные не включаем)
        if 'all_advices' not in action_log:
            action_log['all_advices'] = []
        
        for item in actionable_items:
            advice_id = str(uuid.uuid4())[:8]
            action_log['all_advices'].append({
                'id': advice_id,
                'text': item.get('text', ''),
                'type': item.get('type', 'unknown'),
                'section': item.get('section', 'general'),  # now, this_month, future
                'priority': item.get('priority', 'normal'),  # urgent, quick_win, long_term, actionable
                'message_id': assistant_msg.id,
                'created_at': timezone.now().isoformat(),
                'completed': False,
            })
        
        session.action_log = action_log
    except Exception:
        pass
    
    # Обновляем время сессии
    session.save()
    
    # Группируем советы по секциям (now, this_month, future)
    advice_by_section = {
        'now': [],
        'this_month': [],
        'future': [],
        'general': [],
    }
    for item in actionable_items:
        section = item.get('section', 'general')
        if section in advice_by_section:
            advice_by_section[section].append(item)
        else:
            advice_by_section['general'].append(item)
    
    # Получаем активные (не выполненные) советы из action_log
    active_advices = []
    try:
        action_log = session.action_log or {}
        all_advices = action_log.get('all_advices', [])
        active_advices = [a for a in all_advices if not a.get('completed', False)]
    except Exception:
        pass
    
    # Возвращаем ответ с историей
    response_data = {
        'ok': True,
        'reply': reply,
        'session_id': session_id,
        'message_id': assistant_msg.id,
        'used_local': use_local,
        'anonymize': anonymize,
        'actionable_items': actionable_items,  # Все советы из текущего ответа
        'actionable_by_section': advice_by_section,  # Советы, сгруппированные по секциям
        'actionable_count': len(actionable_items),
        'active_advices': active_advices,  # Все активные (не выполненные) советы из сессии
        'active_advices_count': len(active_advices),
        # 🚀 NEW: WOW-features
        'query_type': query_type,  # Тип запроса (trends/anomalies/advice/etc)
        'confidence': confidence_data,  # Confidence score данные
    }
    
    # Добавляем health score если он был рассчитан
    if health_score_data:
        response_data['health_score'] = health_score_data
    
    return JsonResponse(response_data)


@login_required
def user_settings_api(request):
    """Чтение/сохранение приватных настроек пользователя.
    Храним дополнительные флаги в сессии, чтобы избежать миграций.
    persist: encryption_enabled, local_mode_only в профиле, остальное в сессии.
    """
    # Ensure profile exists
    profile = getattr(request.user, 'teen_profile', None)
    if profile is None:
        # Fallback to 'profile' just in case or try to create
        profile = getattr(request.user, 'profile', None)
        
    if profile is None:
        from django.contrib.auth.models import User
        from .models import UserProfile
        # Use get_or_create to avoid race conditions and IntegrityError
        profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return JsonResponse({
            'encryption_enabled': bool(getattr(profile, 'encryption_enabled', True)),
            'local_mode_only': bool(getattr(profile, 'local_mode_only', False)),
            'auto_clear_file_on_import': bool(getattr(profile, 'auto_clear_file_on_import', False)),
            'auto_remove_duplicates': bool(getattr(profile, 'auto_remove_duplicates', False)),
            'anonymize_enabled': bool(request.session.get('anonymize_enabled', True)),
            'llm_provider': request.session.get('llm_provider', 'openrouter'),
            'llm_model': request.session.get('llm_model', getattr(settings, 'LLM_MODEL', 'deepseek-chat-v3.1:free')),
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            data = {}

        # Persist in profile
        if 'encryption_enabled' in data:
            profile.encryption_enabled = bool(data['encryption_enabled'])
        if 'local_mode_only' in data:
            profile.local_mode_only = bool(data['local_mode_only'])
        if 'auto_clear_file_on_import' in data:
            profile.auto_clear_file_on_import = bool(data['auto_clear_file_on_import'])
        if 'auto_remove_duplicates' in data:
            profile.auto_remove_duplicates = bool(data['auto_remove_duplicates'])
        profile.save()

        # Session-scoped prefs (no migrations needed)
        if 'anonymize_enabled' in data:
            request.session['anonymize_enabled'] = bool(data['anonymize_enabled'])
        if 'llm_provider' in data:
            request.session['llm_provider'] = str(data['llm_provider'])
        if 'llm_model' in data:
            request.session['llm_model'] = str(data['llm_model'])
        if 'use_local' in data:
            request.session['use_local_llm'] = bool(data['use_local'])

        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


@login_required
def delete_all_data_api(request):
    """Удаляет ВСЕ данные пользователя по запросу (one-click)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    try:
        Income.objects.filter(user=request.user).delete()
        Expense.objects.filter(user=request.user).delete()
        Event.objects.filter(user=request.user).delete()
        Document.objects.filter(user=request.user).delete()
        ChatSession.objects.filter(user=request.user).delete()
        # Uploaded files: delete files on disk
        for f in UploadedFile.objects.filter(user=request.user):
            try:
                f.file.delete(save=False)
            except Exception:
                pass
            f.delete()
        return JsonResponse({'ok': True, 'message': 'Все данные удалены'})
    except Exception as ex:
        return JsonResponse({'ok': False, 'error': str(ex)}, status=500)


@login_required
def export_all_data_api(request):
    """Возвращает все пользовательские данные в JSON для локального шифрования на клиенте."""
    # Build datasets
    incomes = list(Income.objects.filter(user=request.user).values('amount', 'date', 'category', 'description', 'tags'))
    expenses = list(Expense.objects.filter(user=request.user).values('amount', 'date', 'category', 'description', 'tags'))
    events = list(Event.objects.filter(user=request.user).values('date', 'title', 'description'))
    documents = list(Document.objects.filter(user=request.user).values('id', 'doc_type', 'params', 'generated_text', 'created_at'))
    # Chat history
    sessions_payload = []
    for s in ChatSession.objects.filter(user=request.user).order_by('created_at'):
        msgs = list(ChatMessage.objects.filter(session=s).order_by('created_at').values('role', 'content', 'created_at'))
        sessions_payload.append({
            'session_id': s.session_id,
            'title': s.title,
            'created_at': s.created_at,
            'updated_at': s.updated_at,
            'messages': msgs,
        })

    return JsonResponse({
        'incomes': incomes,
        'expenses': expenses,
        'events': events,
        'documents': documents,
        'chat_sessions': sessions_payload,
    })


class IncomeListView(ListView):
    model = Income
    template_name = 'income_list.html'
    context_object_name = 'items'
    
    def get_queryset(self):
        qs = Income.objects.filter(user=self.request.user)
        # Фильтр по файлу
        file_id = self.request.GET.get('file_id')
        if file_id:
            try:
                qs = qs.filter(source_file_id=int(file_id))
            except (ValueError, TypeError):
                pass
        return qs.order_by('-date', '-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем все файлы пользователя с количеством транзакций
        from django.db.models import Count
        files = UploadedFile.objects.filter(
            user=self.request.user,
            file_type__in=['csv', 'xlsx', 'xls']
        ).order_by('-uploaded_at')
        context['source_files'] = files
        file_id = self.request.GET.get('file_id')
        context['selected_file_id'] = int(file_id) if file_id and file_id.isdigit() else None
        return context


class IncomeCreateView(CreateView):
    model = Income
    form_class = IncomeForm
    template_name = 'income_form.html'
    success_url = reverse_lazy('core:income_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем существующие категории из БД для текущего пользователя
        existing_categories = Income.objects.filter(
            user=self.request.user
        ).values_list('category', flat=True).distinct().order_by('category')
        context['existing_categories'] = [cat for cat in existing_categories if cat]
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        super().form_valid(form)
        # Редирект обратно на форму с параметром success для показа уведомления и автосброса
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        messages.success(self.request, 'Доход успешно добавлен!')
        return HttpResponseRedirect(f"{reverse('core:income_create')}?success=1")


class IncomeUpdateView(UpdateView):
    model = Income
    form_class = IncomeForm
    template_name = 'income_form.html'
    success_url = reverse_lazy('core:income_list')
    
    def get_queryset(self):
        return Income.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем существующие категории из БД для текущего пользователя
        existing_categories = Income.objects.filter(
            user=self.request.user
        ).values_list('category', flat=True).distinct().order_by('category')
        context['existing_categories'] = [cat for cat in existing_categories if cat]
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Доход успешно обновлен!')
        return response


class IncomeDeleteView(DeleteView):
    model = Income
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('core:income_list')
    
    def get_queryset(self):
        return Income.objects.filter(user=self.request.user)


@login_required
def export_income_csv(request):
    qs = Income.objects.filter(user=request.user).order_by('date')
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename=incomes.csv'
    resp.write('date,amount,category,description\n')
    for o in qs:
        desc = (o.description or '').replace('\n', ' ').replace(',', ' ')
        resp.write(f"{o.date},{o.amount},{o.category},{desc}\n")
    return resp


class ExpenseListView(ListView):
    model = Expense
    template_name = 'expense_list.html'
    context_object_name = 'items'
    
    def get_queryset(self):
        qs = Expense.objects.filter(user=self.request.user)
        # Фильтр по файлу
        file_id = self.request.GET.get('file_id')
        if file_id:
            try:
                qs = qs.filter(source_file_id=int(file_id))
            except (ValueError, TypeError):
                pass
        return qs.order_by('-date', '-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем все файлы пользователя с количеством транзакций
        from django.db.models import Count
        files = UploadedFile.objects.filter(
            user=self.request.user,
            file_type__in=['csv', 'xlsx', 'xls']
        ).order_by('-uploaded_at')
        context['source_files'] = files
        file_id = self.request.GET.get('file_id')
        context['selected_file_id'] = int(file_id) if file_id and file_id.isdigit() else None
        return context


class ExpenseCreateView(CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense_form.html'
    success_url = reverse_lazy('core:expense_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем существующие категории из БД для текущего пользователя
        existing_categories = Expense.objects.filter(
            user=self.request.user
        ).values_list('category', flat=True).distinct().order_by('category')
        context['existing_categories'] = [cat for cat in existing_categories if cat]
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        auto = form.cleaned_data.get('auto_categorize')
        if auto:
            predictor = ExpenseAutoCategorizer()
            suggested = predictor.predict_category(form.cleaned_data.get('description') or '')
            if suggested:
                form.instance.category = suggested
        super().form_valid(form)
        # Редирект обратно на форму с параметром success для показа уведомления и автосброса
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        messages.success(self.request, 'Расход успешно добавлен!')
        return HttpResponseRedirect(f"{reverse('core:expense_create')}?success=1")


class ExpenseUpdateView(UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense_form.html'
    success_url = reverse_lazy('core:expense_list')
    
    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем существующие категории из БД для текущего пользователя
        existing_categories = Expense.objects.filter(
            user=self.request.user
        ).values_list('category', flat=True).distinct().order_by('category')
        context['existing_categories'] = [cat for cat in existing_categories if cat]
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Расход успешно обновлен!')
        return response


class ExpenseDeleteView(DeleteView):
    model = Expense
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('core:expense_list')
    
    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)


@login_required
def export_expense_csv(request):
    qs = Expense.objects.filter(user=request.user).order_by('date')
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename=expenses.csv'
    resp.write('date,amount,category,description\n')
    for o in qs:
        desc = (o.description or '').replace('\n', ' ').replace(',', ' ')
        resp.write(f"{o.date},{o.amount},{o.category},{desc}\n")
    return resp


class EventListView(ListView):
    model = Event
    template_name = 'event_list.html'
    context_object_name = 'items'
    
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user).order_by('-date', '-id')


class EventCreateView(CreateView):
    model = Event
    form_class = EventForm
    template_name = 'event_form.html'
    success_url = reverse_lazy('core:event_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class EventUpdateView(UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'event_form.html'
    success_url = reverse_lazy('core:event_list')
    
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user)


class EventDeleteView(DeleteView):
    model = Event
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('core:event_list')
    
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user)


class DocumentListView(ListView):
    model = Document
    template_name = 'document_list.html'
    context_object_name = 'items'
    
    def get_queryset(self):
        return Document.objects.filter(user=self.request.user).order_by('-created_at', '-id')


class DocumentCreateView(CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'document_form.html'
    success_url = reverse_lazy('core:document_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class DocumentUpdateView(UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'document_form.html'
    success_url = reverse_lazy('core:document_list')
    
    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)


class DocumentDeleteView(DeleteView):
    model = Document
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('core:document_list')
    
    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)


@login_required
def ai_recommendations(request):
    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)
    forecast = forecast_next_month_profit(incomes, expenses)
    recs = build_recommendations(incomes, expenses)
    return render(request, 'ai_recommendations.html', {
        'forecast': forecast,
        'recommendations': recs,
    })


def document_generate_view(request):
    text = None
    if request.method == 'POST':
        doc_type = request.POST.get('doc_type', 'contract')
        params = {
            'client': request.POST.get('client', ''),
            'total': request.POST.get('total', ''),
            'details': request.POST.get('details', ''),
        }
        text = generate_document_text(doc_type, params)
    return render(request, 'document_generate.html', {'generated_text': text})


# ============================================================================
# АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ
# ============================================================================

def register_view(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('core:workspace')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешна! Добро пожаловать!')
            return redirect('core:workspace')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """Вход в систему"""
    if request.user.is_authenticated:
        return redirect('core:workspace')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                next_url = request.GET.get('next', 'core:workspace')
                return redirect(next_url)
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


# ============================================================================
# ИСТОРИЯ ЧАТОВ И ЭКСПОРТ
# ============================================================================

@login_required
def chat_sessions_api(request):
    """API для получения списка сессий чата пользователя"""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')
    
    # Фильтрация по поисковому запросу
    search = request.GET.get('search', '').strip()
    if search:
        sessions = sessions.filter(
            Q(title__icontains=search) | 
            Q(session_id__icontains=search) |
            Q(messages__content__icontains=search)
        ).distinct()
    
    # Пагинация
    page = int(request.GET.get('page', 1))
    page_size = min(50, int(request.GET.get('page_size', 20)))
    paginator = Paginator(sessions, page_size)
    page_obj = paginator.get_page(page)
    
    sessions_data = []
    for session in page_obj:
        sessions_data.append({
            'id': session.id,
            'session_id': session.session_id,
            'title': session.title or 'Без названия',
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'message_count': session.messages.count(),
            'file_ids': list(session.files.values_list('id', flat=True)),
            'data_summaries': session.data_summaries or {},
        })
    
    return JsonResponse({
        'sessions': sessions_data,
        'total': paginator.count,
        'page': page,
        'page_size': page_size,
        'num_pages': paginator.num_pages,
    })


@login_required
def rename_chat_session(request, session_id):
    """Переименовать чат-сессию."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        payload = {}
    new_title = (payload.get('title') or '').strip()
    if not new_title:
        return JsonResponse({'ok': False, 'error': 'Пустое название'}, status=400)
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        session.title = new_title[:200]
        session.save()
        return JsonResponse({'ok': True, 'title': session.title})
    except ChatSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)


@login_required
def chat_history_api(request, session_id):
    """API для получения истории конкретной сессии чата"""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)
    
    messages = ChatMessage.objects.filter(session=session).order_by('created_at')
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'is_useful': msg.is_useful,
            'metadata': msg.metadata or {},
        })
    
    # Получаем активные (не выполненные) советы
    action_log = session.action_log or {}
    all_advices = action_log.get('all_advices', [])
    active_advices = [a for a in all_advices if not a.get('completed', False)]
    completed_advices = [a for a in all_advices if a.get('completed', False)]
    
    return JsonResponse({
        'ok': True,
        'session': {
            'id': session.id,
            'session_id': session.session_id,
            'title': session.title,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'file_ids': list(session.files.values_list('id', flat=True)),
            'data_summaries': session.data_summaries or {},
            'action_log': {
                'advices_given': action_log.get('advices_given', 0),
                'advices_completed': action_log.get('advices_completed', 0),
                'active_advices_count': len(active_advices),
            },
        },
        'messages': messages_data,
        'active_advices': active_advices,  # Только активные (не выполненные) советы
        'completed_advices': completed_advices,  # Выполненные советы (для истории)
    })


@login_required
def delete_chat_session(request, session_id):
    """Удаление сессии чата"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        session.delete()
        return JsonResponse({'ok': True, 'message': 'Сессия удалена'})
    except ChatSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)


@login_required
def clear_chat_session(request, session_id):
    """Очистка сообщений в сессии (сохраняет сессию, удаляет только сообщения)"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        ChatMessage.objects.filter(session=session).delete()
        return JsonResponse({'ok': True, 'message': 'Чат очищен'})
    except ChatSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)


@login_required
def export_chat_history(request, session_id):
    """Экспорт истории чата в выбранном формате"""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        messages.error(request, 'Сессия не найдена')
        return redirect('core:workspace')
    
    format_type = request.GET.get('format', 'csv').lower()
    
    # Получаем все сообщения
    messages_list = ChatMessage.objects.filter(session=session).order_by('created_at')
    messages_data = []
    for msg in messages_list:
        messages_data.append({
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at,
        })
    
    session_title = session.title or f"Chat {session.session_id[:8]}"
    
    try:
        if format_type == 'csv':
            csv_io = export_chat_to_csv(messages_data, session_title)
            response = HttpResponse(csv_io.getvalue(), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="chat_{session.session_id[:8]}.csv"'
            return response
        
        elif format_type == 'docx':
            docx_io = export_chat_to_docx(messages_data, session_title)
            response = HttpResponse(docx_io.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="chat_{session.session_id[:8]}.docx"'
            return response
        
        elif format_type == 'pdf':
            pdf_io = export_chat_to_pdf(messages_data, session_title)
            response = HttpResponse(pdf_io.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="chat_{session.session_id[:8]}.pdf"'
            return response
        
        else:
            messages.error(request, 'Неподдерживаемый формат экспорта')
            return redirect('core:workspace')
    
    except ImportError as e:
        messages.error(request, f'Ошибка экспорта: {str(e)}. Установите необходимые библиотеки.')
        return redirect('core:workspace')
    except Exception as e:
        messages.error(request, f'Ошибка экспорта: {str(e)}')
        return redirect('core:workspace')


# ============================================================================
# УПРАВЛЕНИЕ ФАЙЛАМИ
# ============================================================================

@login_required
def uploaded_files_api(request):
    """API для получения списка загруженных файлов пользователя"""
    files = UploadedFile.objects.filter(user=request.user).order_by('-uploaded_at')
    
    files_data = []
    for f in files:
        files_data.append({
            'id': f.id,
            'original_name': f.original_name,
            'file_type': f.file_type,
            'file_size': f.file_size,
            'uploaded_at': f.uploaded_at.isoformat(),
            'processed': f.processed,
        })
    
    return JsonResponse({'files': files_data})


@login_required
def delete_uploaded_file(request, file_id):
    """Удаление загруженного файла"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        file_obj = UploadedFile.objects.get(id=file_id, user=request.user)
        file_obj.file.delete()  # Удаляем файл с диска
        file_obj.delete()  # Удаляем запись из БД
        return JsonResponse({'ok': True, 'message': 'Файл удален'})
    except UploadedFile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Файл не найден'}, status=404)


@login_required
def delete_transactions_by_file(request, file_id):
    """Удаление всех транзакций (доходов и расходов), связанных с файлом"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        file_obj = UploadedFile.objects.get(id=file_id, user=request.user)
        income_count = Income.objects.filter(user=request.user, source_file=file_obj).count()
        expense_count = Expense.objects.filter(user=request.user, source_file=file_obj).count()
        
        Income.objects.filter(user=request.user, source_file=file_obj).delete()
        Expense.objects.filter(user=request.user, source_file=file_obj).delete()
        
        return JsonResponse({
            'ok': True, 
            'message': f'Удалено: доходов {income_count}, расходов {expense_count}',
            'deleted': {'incomes': income_count, 'expenses': expense_count}
        })
    except UploadedFile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Файл не найден'}, status=404)


@login_required
def delete_transactions_by_files(request):
    """Массовое удаление транзакций из нескольких файлов"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    import json
    try:
        data = json.loads(request.body)
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            return JsonResponse({'ok': False, 'error': 'Не указаны ID файлов'}, status=400)
        
        files = UploadedFile.objects.filter(id__in=file_ids, user=request.user)
        total_income = 0
        total_expense = 0
        
        for file_obj in files:
            income_count = Income.objects.filter(user=request.user, source_file=file_obj).count()
            expense_count = Expense.objects.filter(user=request.user, source_file=file_obj).count()
            total_income += income_count
            total_expense += expense_count
            
            Income.objects.filter(user=request.user, source_file=file_obj).delete()
            Expense.objects.filter(user=request.user, source_file=file_obj).delete()
        
        return JsonResponse({
            'ok': True,
            'message': f'Удалено из {len(files)} файлов: доходов {total_income}, расходов {total_expense}',
            'deleted': {'incomes': total_income, 'expenses': total_expense, 'files': len(files)}
        })
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Неверный JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def find_duplicates_api(request):
    """API для поиска дубликатов транзакций"""
    file_id = request.GET.get('file_id')
    source_file = None
    
    if file_id:
        try:
            source_file = UploadedFile.objects.get(id=int(file_id), user=request.user)
        except (UploadedFile.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': 'Файл не найден'}, status=404)
    
    duplicates = find_duplicates(request.user, source_file)
    
    # Форматируем результат для удобства
    result = {
        'ok': True,
        'duplicates': {
            'incomes': [],
            'expenses': []
        }
    }
    
    # Для доходов
    for dup in duplicates['incomes']:
        transactions = Income.objects.filter(id__in=dup['transactions'], user=request.user)
        result['duplicates']['incomes'].append({
            'count': len(dup['transactions']),
            'transactions': [
                {
                    'id': t.id,
                    'date': t.date.isoformat(),
                    'amount': t.amount,
                    'category': t.category,
                    'description': t.description,
                    'source_file': t.source_file.original_name if t.source_file else None
                }
                for t in transactions
            ]
        })
    
    # Для расходов
    for dup in duplicates['expenses']:
        transactions = Expense.objects.filter(id__in=dup['transactions'], user=request.user)
        result['duplicates']['expenses'].append({
            'count': len(dup['transactions']),
            'transactions': [
                {
                    'id': t.id,
                    'date': t.date.isoformat(),
                    'amount': t.amount,
                    'category': t.category,
                    'description': t.description,
                    'source_file': t.source_file.original_name if t.source_file else None
                }
                for t in transactions
            ]
        })
    
    return JsonResponse(result)


@login_required
def delete_duplicates_api(request):
    """API для удаления выбранных дубликатов"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    import json
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])
        transaction_type = data.get('type')  # 'income' or 'expense'
        
        if not transaction_ids or not transaction_type:
            return JsonResponse({'ok': False, 'error': 'Не указаны ID транзакций или тип'}, status=400)
        
        deleted_count = 0
        if transaction_type == 'income':
            deleted_count = Income.objects.filter(id__in=transaction_ids, user=request.user).delete()[0]
        elif transaction_type == 'expense':
            deleted_count = Expense.objects.filter(id__in=transaction_ids, user=request.user).delete()[0]
        else:
            return JsonResponse({'ok': False, 'error': 'Неверный тип транзакции'}, status=400)
        
        return JsonResponse({
            'ok': True,
            'message': f'Удалено {deleted_count} транзакций',
            'deleted_count': deleted_count
        })
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Неверный JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ============================================================================
# СРАВНЕНИЕ ЧАТОВ/ПЕРИОДОВ
# ============================================================================

@login_required
def compare_chats_api(request):
    """Сравнение доходов/расходов для выбранных чатов или периодов.
    Принимает JSON:
    {
      "items": [
         {"label": "Апрель", "start": "2025-04-01", "end": "2025-04-30", "session_id": "..."},
         {"label": "Май", "start": "2025-05-01", "end": "2025-05-31"}
      ]
    }
    Возвращает агрегаты для визуализации (по месяцам и категориям).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    items = payload.get('items') or []
    if not items:
        return JsonResponse({'ok': False, 'error': 'No items to compare'}, status=400)

    results = []
    for it in items:
        label = it.get('label') or 'Без названия'
        start = it.get('start')
        end = it.get('end')
        qs_in = Income.objects.filter(user=request.user)
        qs_ex = Expense.objects.filter(user=request.user)
        if start:
            qs_in = qs_in.filter(date__gte=start)
            qs_ex = qs_ex.filter(date__gte=start)
        if end:
            qs_in = qs_in.filter(date__lte=end)
            qs_ex = qs_ex.filter(date__lte=end)

        # По месяцам
        def month_key(d):
            return f"{d.year:04d}-{d.month:02d}"

        month_in = {}
        month_ex = {}
        cat_in = {}
        cat_ex = {}
        for o in qs_in:
            mk = month_key(o.date)
            month_in[mk] = month_in.get(mk, 0.0) + float(o.amount)
            cat_in[o.category] = cat_in.get(o.category, 0.0) + float(o.amount)
        for o in qs_ex:
            mk = month_key(o.date)
            month_ex[mk] = month_ex.get(mk, 0.0) + float(o.amount)
            cat_ex[o.category] = cat_ex.get(o.category, 0.0) + float(o.amount)

        results.append({
            'label': label,
            'start': start,
            'end': end,
            'income_by_month': month_in,
            'expense_by_month': month_ex,
            'income_by_category': cat_in,
            'expense_by_category': cat_ex,
        })

    return JsonResponse({'ok': True, 'results': results})


# ============================================================================
# ACTION LOG И SUCCESS CASES
# ============================================================================

@login_required
def mark_message_useful(request, message_id):
    """Отметка сообщения как полезного (success-case)"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        message = ChatMessage.objects.get(id=message_id, session__user=request.user)
        message.is_useful = True
        message.save()
        
        # Сохраняем в success_cases пользователя
        profile = getattr(request.user, 'profile', None)
        if profile:
            success_cases = list(profile.success_cases or [])
            success_cases.append({
                'message_id': message.id,
                'session_id': message.session.session_id,
                'content': message.content[:500],  # Первые 500 символов
                'created_at': timezone.now().isoformat(),
                'actionable_items': message.metadata.get('actionable_items', []),
            })
            profile.success_cases = success_cases
            profile.save()
        
        return JsonResponse({'ok': True, 'message': 'Сообщение отмечено как полезное'})
    except ChatMessage.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сообщение не найдено'}, status=404)


@login_required
def mark_advice_completed(request, session_id):
    """Отметка совета как выполненного. Выполненные советы остаются в истории, но исключаются из активных."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        advice_index = payload.get('advice_index')  # Индекс в списке all_advices
        advice_id = payload.get('advice_id')  # Альтернативно: ID совета
        
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        action_log = dict(session.action_log or {})
        
        if 'all_advices' not in action_log:
            return JsonResponse({'ok': False, 'error': 'Нет советов в сессии'}, status=400)
        
        all_advices = list(action_log['all_advices'])
        
        # Находим совет по индексу или ID
        found = False
        if advice_index is not None and 0 <= advice_index < len(all_advices):
            all_advices[advice_index]['completed'] = True
            all_advices[advice_index]['completed_at'] = timezone.now().isoformat()
            found = True
        elif advice_id:
            for advice in all_advices:
                if advice.get('id') == advice_id:
                    advice['completed'] = True
                    advice['completed_at'] = timezone.now().isoformat()
                    found = True
                    break
        
        if not found:
            return JsonResponse({'ok': False, 'error': 'Совет не найден'}, status=404)
        
        action_log['all_advices'] = all_advices
        action_log['advices_completed'] = sum(1 for a in all_advices if a.get('completed', False))
        
        # Сохраняем историю выполненных советов отдельно
        if 'completed_advices_history' not in action_log:
            action_log['completed_advices_history'] = []
        completed_advice = next((a for a in all_advices if a.get('id') == advice_id or (advice_index is not None and all_advices.index(a) == advice_index)), None)
        if completed_advice:
            action_log['completed_advices_history'].append(completed_advice)
        
        session.action_log = action_log
        session.save()
        
        # Возвращаем только активные (не выполненные) советы
        active_advices = [a for a in all_advices if not a.get('completed', False)]
        
        return JsonResponse({
            'ok': True,
            'completed_count': action_log['advices_completed'],
            'active_count': len(active_advices),
        })
    except ChatSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def get_action_stats(request, session_id=None):
    """Получение статистики по советам и действиям"""
    try:
        # session_id может быть передан через URL или GET параметр
        if not session_id:
            session_id = request.GET.get('session_id')
        
        if session_id:
            sessions = ChatSession.objects.filter(session_id=session_id, user=request.user)
        else:
            sessions = ChatSession.objects.filter(user=request.user)
        
        total_advices = 0
        completed_advices = 0
        useful_messages = 0
        total_messages = 0
        
        for session in sessions:
            action_log = session.action_log or {}
            total_advices += action_log.get('advices_given', 0)
            completed_advices += action_log.get('advices_completed', 0)
            total_messages += action_log.get('total_messages', 0)
        
        useful_messages = ChatMessage.objects.filter(
            session__user=request.user,
            is_useful=True
        ).count()
        
        return JsonResponse({
            'ok': True,
            'stats': {
                'total_advices': total_advices,
                'completed_advices': completed_advices,
                'completion_rate': round(completed_advices / total_advices * 100, 2) if total_advices > 0 else 0,
                'useful_messages': useful_messages,
                'total_messages': total_messages,
            }
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def export_chat_markdown(request, session_id):
    """Экспорт истории чата в Markdown формат"""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        messages.error(request, 'Сессия не найдена')
        return redirect('workspace')
    
    # Получаем все сообщения
    chat_messages = ChatMessage.objects.filter(session=session).order_by('created_at')
    
    # Формируем Markdown
    md_lines = []
    md_lines.append(f"# {session.title or 'Чат-сессия'}\n")
    md_lines.append(f"**Сессия:** {session.session_id}\n")
    md_lines.append(f"**Создана:** {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append(f"**Обновлена:** {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append(f"**Дата экспорта:** {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append("\n---\n")
    
    # Статистика по советам
    action_log = session.action_log or {}
    if action_log:
        md_lines.append("## 📊 Статистика\n")
        md_lines.append(f"- **Всего советов:** {action_log.get('advices_given', 0)}\n")
        md_lines.append(f"- **Выполнено:** {action_log.get('advices_completed', 0)}\n")
        md_lines.append(f"- **Всего сообщений:** {action_log.get('total_messages', 0)}\n")
        md_lines.append("\n---\n")
    
    # Сообщения
    md_lines.append("## 💬 История диалога\n\n")
    
    for msg in chat_messages:
        role_icon = "👤" if msg.role == "user" else "🤖" if msg.role == "assistant" else "⚙️"
        role_name = "Пользователь" if msg.role == "user" else "AI Ассистент" if msg.role == "assistant" else "Система"
        
        md_lines.append(f"### {role_icon} {role_name}\n")
        md_lines.append(f"*{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        
        # Содержимое сообщения (уже в markdown)
        md_lines.append(f"{msg.content}\n\n")
        
        # Метаданные (actionable items, полезность)
        if msg.metadata:
            actionable_items = msg.metadata.get('actionable_items', [])
            if actionable_items:
                md_lines.append("**Советы из этого сообщения:**\n")
                for item in actionable_items:
                    md_lines.append(f"- {item.get('text', '')}\n")
                md_lines.append("\n")
        
        if msg.is_useful:
            md_lines.append("⭐ *Отмечено как полезное*\n\n")
        
        md_lines.append("---\n\n")
    
    # Actionable советы отдельным разделом
    if action_log.get('all_advices'):
        md_lines.append("## ✅ Все советы\n\n")
        for idx, advice in enumerate(action_log['all_advices'], 1):
            status = "✅ Выполнено" if advice.get('completed') else "⏳ В ожидании"
            md_lines.append(f"{idx}. {advice.get('text', '')} - {status}\n")
        md_lines.append("\n")
    
    # Формируем ответ
    response = HttpResponse(''.join(md_lines), content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="chat_{session.session_id[:8]}.md"'
    return response

@login_required
def ai_reclassify_others(request):
    """
    Finds all 'other' transactions for the user and tries to reclassify them using AI.
    """
    from core.utils.ai_utils import ai_categorize_batch
    
    other_incomes = list(Income.objects.filter(user=request.user, income_type='other'))
    other_expenses = list(Expense.objects.filter(user=request.user, expense_type='other'))
    
    if not other_incomes and not other_expenses:
        return JsonResponse({'ok': True, 'message': 'Нет транзакций в категории "Другое"'})
    
    reclassified_count = 0
    
    # Process in chunks to avoid huge prompts
    def process_batch(items, item_type):
        nonlocal reclassified_count
        chunk_size = 20
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            transactions_data = [{'description': it.description or ''} for it in chunk]
            ai_cats = ai_categorize_batch(transactions_data, item_type)
            for it, cat in zip(chunk, ai_cats):
                if cat != 'other':
                    if item_type == 'income': 
                        it.income_type = cat
                    else:
                        it.expense_type = cat
                    it.save()
                    reclassified_count += 1

    process_batch(other_incomes, 'income')
    process_batch(other_expenses, 'expense')
                
    return JsonResponse({'ok': True, 'message': f'Обработано {len(other_incomes) + len(other_expenses)} транзакций. Изменено категорий: {reclassified_count}'})

# ==============================================================================
# TEEN-FOCUSED VIEWS (Originally from views_teen.py)
# ==============================================================================

@login_required
def goals_view(request):
    """
    Goals management page with progress visualization
    """
    try:
        user = request.user
        
        # Get all user goals
        goals = user.goals.all().order_by('-created_at')
        
        # Categorize goals
        active_goals = goals.filter(status='active')
        completed_goals = goals.filter(status='completed')
        
        # Calculate total saved amount
        total_saved = sum([float(goal.current_amount) for goal in active_goals])
        
        # Get gamification data for goals
        goal_achievements = UserAchievement.objects.filter(
            user=user,
            achievement__category='goal'
        ).select_related('achievement')
        
        context = {
            'active_goals': active_goals,
            'completed_goals': completed_goals,
            'total_saved': total_saved,
            'goal_achievements': goal_achievements,
        }
        
        return render(request, 'teen/goals.html', context)
        
    except Exception as e:
        logger.error(f"Error in goals view: {e}")
        messages.error(request, "Произошла ошибка при загрузке целей")
        return redirect('core:dashboard')


@login_required
def create_goal(request):
    """
    Create new savings goal with AI-powered suggestions
    """
    if request.method == 'POST':
        try:
            user = request.user
            
            # Extract form data
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            target_amount = float(request.POST.get('target_amount', 0))
            category = request.POST.get('category', 'other')
            target_date_str = request.POST.get('target_date', '')
            
            if not title or target_amount <= 0 or not target_date_str:
                messages.error(request, "Заполните все обязательные поля")
                return redirect('core:goals')
            
            # Parse target date
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            
            # Create goal
            goal = UserGoal.objects.create(
                user=user,
                title=title,
                description=description,
                target_amount=target_amount,
                category=category,
                target_date=target_date,
                weekly_saving_suggestion=0  # Will be calculated by AI
            )
            
            # Get AI recommendation
            try:
                ai_advice = teen_coach.get_personalized_savings_advice(user, goal)
                goal.ai_recommendation = ai_advice.get('advice', '')
                goal.weekly_saving_suggestion = ai_advice.get('weekly_target', 0)
                goal.save()
            except Exception as e:
                logger.error(f"Error getting AI advice for goal: {e}")
            
            # Update user progress
            progress = user.progress
            progress.goals_created += 1
            progress.last_goal_update = timezone.now()
            progress.save()
            
            # Check for achievements
            achievements = gamification_engine.check_user_achievements(user)
            if achievements:
                gamification_engine.unlock_achievements(user, achievements)
                messages.success(request, "🎉 Поздравляем! Вы получили новое достижение!")
            
            messages.success(request, f"Цель '{title}' создана успешно!")
            return redirect('core:goals')
            
        except ValueError:
            messages.error(request, "Некорректная сумма или дата")
            return redirect('core:goals')
        except Exception as e:
            logger.error(f"Error creating goal: {e}")
            messages.error(request, "Произошла ошибка при создании цели")
            return redirect('core:goals')
    
    return redirect('core:goals')


@login_required
def update_goal_progress(request, goal_id):
    """
    Update progress on a savings goal
    """
    if request.method == 'POST':
        try:
            user = request.user
            goal = get_object_or_404(UserGoal, id=goal_id, user=user)
            
            new_amount = float(request.POST.get('current_amount', 0))
            
            if new_amount < 0:
                messages.error(request, "Сумма не может быть отрицательной")
                return redirect('core:goals')
            
            # Update goal
            goal.current_amount = new_amount
            goal.save()
            
            # Check if goal is completed
            if goal.progress_percentage() >= 100 and goal.status == 'active':
                goal.status = 'completed'
                goal.completed_at = timezone.now()
                goal.save()
                
                # Update user profile
                profile = user.teen_profile
                profile.goals_achieved += 1
                profile.save()
                
                # Update progress
                progress = user.progress
                progress.goals_achieved += 1
                progress.save()
                
                messages.success(request, "🎉 Поздравляем! Вы достигли своей цели!")
            else:
                messages.success(request, "Прогресс обновлен!")
            
            # Check for achievements
            achievements = gamification_engine.check_user_achievements(user)
            if achievements:
                unlocked = gamification_engine.unlock_achievements(user, achievements)
                if unlocked['unlocked_count'] > 0:
                    messages.success(request, "🏆 Получено новое достижение!")
            
            return redirect('core:goals')
            
        except ValueError:
            messages.error(request, "Некорректная сумма")
            return redirect('core:goals')
        except Exception as e:
            logger.error(f"Error updating goal progress: {e}")
            messages.error(request, "Произошла ошибка при обновлении прогресса")
            return redirect('core:goals')
    
    return redirect('core:goals')


@login_required
def ai_coach(request):
    """
    AI Financial Coach chat interface
    """
    try:
        user = request.user
        profile = user.teen_profile
        
        # Get recent chat sessions
        chat_sessions = user.teen_chat_sessions.order_by('-updated_at')[:10]
        
        # Get current session if specified
        current_session_id = request.GET.get('session')
        current_session = None
        
        if current_session_id:
            current_session = get_object_or_404(
                TeenChatSession, 
                session_id=current_session_id, 
                user=user
            )
            msgs = current_session.teen_messages.order_by('created_at')
        else:
            msgs = []
        
        context = {
            'chat_sessions': chat_sessions,
            'current_session': current_session,
            'messages': msgs,
            'user_age': profile.age or 16,
            'preferred_language': profile.preferred_language,
        }
        
        return render(request, 'teen/ai_coach.html', context)
        
    except Exception as e:
        logger.error(f"Error in AI coach view: {e}")
        messages.error(request, "Произошла ошибка при загрузке AI коуча")
        return redirect('core:dashboard')


@csrf_exempt
@login_required
def chat_with_ai(request):
    """
    Handle chat with AI financial coach
    """
    if request.method == 'POST':
        try:
            user = request.user
            data = json.loads(request.body)
            
            message = data.get('message', '').strip()
            session_id = data.get('session_id')
            
            if not message:
                return JsonResponse({'error': 'Сообщение не может быть пустым'}, status=400)
            
            # Get or create chat session
            if session_id:
                session = get_object_or_404(TeenChatSession, session_id=session_id, user=user)
            else:
                session = TeenChatSession.objects.create(
                    user=user,
                    session_id=f"session_{user.id}_{int(timezone.now().timestamp())}",
                    title=f"Chat - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            
            # Get AI response
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            ai_response_data = loop.run_until_complete(
                teen_coach.get_coaching_response(user, message)
            )
            
            # Save user message
            TeenChatMessage.objects.create(
                session=session,
                role='user',
                content=message
            )
            
            # Save AI response
            TeenChatMessage.objects.create(
                session=session,
                role='teen_coach',
                content=ai_response_data.get('response', 'Извините, произошла ошибка.'),
                confidence_score=ai_response_data.get('confidence'),
                reasoning_explained=ai_response_data.get('ai_reasoning'),
                is_educational=ai_response_data.get('educational_content', False),
                learning_objective=ai_response_data.get('learning_objective'),
                was_actionable=ai_response_data.get('was_actionable', False)
            )
            
            # Update user progress
            progress = user.progress
            progress.ai_conversations += 1
            progress.last_activity = timezone.now()
            progress.save()
            
            # Update user activity for streaks
            gamification_engine.update_user_activity(user)
            
            # Check for achievements
            achievements = gamification_engine.check_user_achievements(user)
            unlocked_count = 0
            if achievements:
                unlocked = gamification_engine.unlock_achievements(user, achievements)
                unlocked_count = unlocked.get('unlocked_count', 0)
                
            return JsonResponse({
                'response': ai_response_data.get('response'),
                'session_id': session.session_id,
                'confidence': ai_response_data.get('confidence'),
                'educational': ai_response_data.get('educational_content', False),
                'actionable': ai_response_data.get('was_actionable', False),
                'reasoning': ai_response_data.get('ai_reasoning'),
                'achievements_unlocked': unlocked_count
            })
            
        except Exception as e:
            logger.error(f"Error in chat with AI: {e}")
            return JsonResponse({'error': 'Произошла ошибка при обработке сообщения'}, status=500)
    
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


@login_required
def learning_modules(request):
    """
    Learning modules and educational content
    """
    try:
        from django.db.models import Max
        # Get published modules
        modules = LearningModule.objects.filter(is_published=True).order_by('difficulty', 'created_at')
        
        # Get user's learning progress
        u_progress = {}
        for module in modules:
            attempts = UserQuizAttempt.objects.filter(user=request.user, quiz__module=module)
            u_progress[module.id] = {
                'attempts': attempts.count(),
                'best_score': attempts.aggregate(max_score=Max('score'))['max_score'] or 0,
                'passed': attempts.filter(passed=True).exists()
            }
        
        context = {
            'modules': modules,
            'user_progress': u_progress,
        }
        
        return render(request, 'teen/learning.html', context)
        
    except Exception as e:
        logger.error(f"Error in learning modules: {e}")
        messages.error(request, "Произошла ошибка при загрузке обучающих материалов")
        return redirect('core:dashboard')


@login_required
def module_detail(request, module_id):
    """
    Individual learning module view
    """
    try:
        module = get_object_or_404(LearningModule, id=module_id, is_published=True)
        
        # Get associated quiz
        quiz = module.quizzes.first()
        quiz_data = None
        
        if quiz:
            questions = quiz.questions.order_by('order')
            quiz_data = {
                'quiz': quiz,
                'questions': questions,
                'questions_count': questions.count()
            }
        
        # Get user's attempts for this module
        user_attempts = []
        if quiz:
            user_attempts = UserQuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz
            ).order_by('-completed_at')
        
        context = {
            'module': module,
            'quiz_data': quiz_data,
            'user_attempts': user_attempts,
        }
        
        return render(request, 'teen/module_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error in module detail: {e}")
        messages.error(request, "Произошла ошибка при загрузке урока")
        return redirect('core:learning')


@login_required
def take_quiz(request, quiz_id):
    """
    Take a quiz for a learning module
    """
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id)
        questions = quiz.questions.order_by('order')
        
        if request.method == 'POST':
            # Process quiz answers
            correct_answers = 0
            total_questions = questions.count()
            answers_data = {}
            
            for question in questions:
                user_answer = request.POST.get(f'question_{question.id}', '')
                correct_answer = question.correct_answer
                
                is_correct = user_answer.lower() == correct_answer.lower()
                if is_correct:
                    correct_answers += 1
                
                answers_data[question.id] = {
                    'user_answer': user_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct
                }
            
            # Calculate score
            score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0
            passed = score >= quiz.passing_score
            
            # Save attempt
            attempt = UserQuizAttempt.objects.create(
                user=request.user,
                quiz=quiz,
                score=score,
                passed=passed,
                answers=answers_data
            )
            
            # Update user progress
            profile = request.user.teen_profile
            if passed:
                profile.quizzes_passed += 1
            profile.lessons_completed += 1
            profile.save()
            
            progress = request.user.progress
            progress.modules_completed += 1
            progress.last_lesson_date = timezone.now()
            progress.save()
            
            # Check for achievements
            achievements = gamification_engine.check_user_achievements(request.user)
            unlocked_count = 0
            if achievements:
                unlocked = gamification_engine.unlock_achievements(request.user, achievements)
                unlocked_count = unlocked.get('unlocked_count', 0)
            
            # Calculate score for Financial IQ
            iq_bonus = 2 if passed else 1
            profile.financial_iq_score = min(100, profile.financial_iq_score + iq_bonus)
            profile.save()
            
            return render(request, 'teen/quiz_result.html', {
                'quiz': quiz,
                'score': score,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'passed': passed,
                'attempt': attempt,
                'answers_data': answers_data,
                'achievements_unlocked': unlocked_count
            })
        
        # GET request - show quiz
        context = {
            'quiz': quiz,
            'questions': questions,
        }
        
        return render(request, 'teen/quiz_form.html', context)
        
    except Exception as e:
        logger.error(f"Error taking quiz: {e}")
        messages.error(request, "Произошла ошибка при загрузке квиза")
        return redirect('core:learning')


@login_required
def scam_awareness(request):
    """
    Scam awareness and detection module
    """
    try:
        # Get user's scam reports
        scam_reports = ScamAlert.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]
        
        # Get statistics
        total_reports = scam_reports.count()
        suspicious_reports = scam_reports.filter(is_suspicious=True).count()
        
        context = {
            'scam_reports': scam_reports,
            'total_reports': total_reports,
            'suspicious_reports': suspicious_reports,
        }
        
        return render(request, 'teen/scam_awareness.html', context)
        
    except Exception as e:
        logger.error(f"Error in scam awareness: {e}")
        messages.error(request, "Произошла ошибка при загрузке модуля защиты")
        return redirect('core:dashboard')


@csrf_exempt
@login_required
def report_scam(request):
    """
    Report potential scam for AI analysis
    """
    if request.method == 'POST':
        try:
            user = request.user
            data = json.loads(request.body)
            
            reported_text = data.get('text', '').strip()
            reported_url = data.get('url', '').strip()
            
            if not reported_text and not reported_url:
                return JsonResponse({'error': 'Укажите текст или URL для проверки'}, status=400)
            
            # Analyze with AI
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            analysis = loop.run_until_complete(
                analyze_potential_scam(reported_text, reported_url, user)
            )
            
            # Save scam alert
            scam_alert = ScamAlert.objects.create(
                user=user,
                reported_text=reported_text,
                reported_url=reported_url,
                is_suspicious=analysis['is_suspicious'],
                severity=analysis['severity'],
                risk_score=analysis['risk_score'],
                red_flags=analysis['red_flags'],
                explanation=analysis['explanation'],
                safe_alternatives=analysis['safe_alternatives']
            )
            
            # Update user progress
            progress = user.progress
            progress.scam_reports += 1
            progress.save()
            
            # Check for achievements
            achievements = gamification_engine.check_user_achievements(user)
            unlocked_count = 0
            if achievements:
                unlocked = gamification_engine.unlock_achievements(user, achievements)
                unlocked_count = unlocked.get('unlocked_count', 0)
            
            return JsonResponse({
                'alert_id': scam_alert.id,
                'is_suspicious': analysis['is_suspicious'],
                'severity': analysis['severity'],
                'risk_score': analysis['risk_score'],
                'explanation': analysis['explanation'],
                'red_flags': analysis['red_flags'],
                'safe_alternatives': analysis['safe_alternatives'],
                'achievements_unlocked': unlocked_count
            })
            
        except Exception as e:
            logger.error(f"Error reporting scam: {e}")
            return JsonResponse({'error': 'Произошла ошибка при анализе'}, status=500)
    
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


async def analyze_potential_scam(text: str, url: str, user) -> Dict[str, Any]:
    """
    Analyze potential scam using AI
    """
    try:
        context = await teen_coach._build_user_context(user)
        
        system_prompt = f"""
Ты - эксперт по кибербезопасности и защите от мошенничества для подростков.
Проанализируй следующий текст или URL на признаки мошенничества.

ПРИЗНАКИ МОШЕННИЧЕСТВА:
- Слишком хорошие предложения (быстрый заработок, бесплатные деньги)
- Давление "ограниченное время"
- Требование личных данных или оплаты вперед
- Необычные способы оплаты (криптовалюта, подарочные карты)
- Поддельные бренды или логотипы
- Орфографические и грамматические ошибки
- Отсутствие контактной информации

Ответь в формате JSON:
{{
    "is_suspicious": true/false,
    "severity": "low/medium/high/critical",
    "risk_score": 0-100,
    "red_flags": ["список красных флагов"],
    "explanation": "подробное объяснение на русском языке",
    "safe_alternatives": ["безопасные альтернативы"]
}}
"""
        
        analysis_text = f"Текст для анализа: {text}\nURL: {url}"
        
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_text}
        ]
        
        response = await llm_manager.chat(msgs, temperature=0.3, max_tokens=800)
        
        # Parse JSON response
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback analysis
            analysis = {
                "is_suspicious": "бесплатн" in text.lower() or "заработок" in text.lower(),
                "severity": "medium",
                "risk_score": 60,
                "red_flags": ["требует анализа специалистом"],
                "explanation": "Потребуется дополнительная проверка этого предложения.",
                "safe_alternatives": ["обратитесь к взрослым за советом"]
            }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing potential scam: {e}")
        return {
            "is_suspicious": False,
            "severity": "low",
            "risk_score": 20,
            "red_flags": [],
            "explanation": "Не удалось провести анализ. Будьте осторожны с незнакомыми предложениями.",
            "safe_alternatives": ["не переходите по подозрительным ссылкам"]
        }


@login_required
def achievements_view(request):
    """
    User achievements and progress tracking
    """
    try:
        user = request.user
        
        # Get user achievements
        user_achievements = UserAchievement.objects.filter(
            user=user
        ).select_related('achievement').order_by('-earned_at')
        
        # Get all available achievements
        all_achievements = Achievement.objects.filter(is_active=True)
        
        # Categorize achievements
        earned_achievement_ids = set(user_achievements.values_list('achievement_id', flat=True))
        
        earned_achievements = []
        available_achievements = []
        
        for achievement in all_achievements:
            if achievement.id in earned_achievement_ids:
                earned_achievements.append(achievement)
            else:
                # Calculate progress
                check_result = gamification_engine._check_single_achievement(user, achievement)
                progress_percent = gamification_engine._calculate_achievement_progress(
                    check_result.progress, achievement.criteria
                )
                available_achievements.append({
                    'achievement': achievement,
                    'progress': progress_percent
                })
        
        # Get gamification data
        gamification_data = gamification_engine.get_user_dashboard_data(user)
        
        context = {
            'earned_achievements': earned_achievements,
            'available_achievements': available_achievements,
            'user_achievements': user_achievements,
            'gamification': gamification_data,
        }
        
        return render(request, 'teen/achievements.html', context)
        
    except Exception as e:
        logger.error(f"Error in achievements view: {e}")
        messages.error(request, "Произошла ошибка при загрузке достижений")
        return redirect('core:dashboard')


@login_required
def toggle_demo_mode(request):
    """
    Toggle demo mode for presentations
    """
    if request.method == 'POST':
        try:
            profile = request.user.teen_profile
            profile.demo_mode = not profile.demo_mode
            profile.save()
            
            st = "включен" if profile.demo_mode else "выключен"
            messages.success(request, f"Демо-режим {st}")
            
        except Exception as e:
            logger.error(f"Error toggling demo mode: {e}")
            messages.error(request, "Произошла ошибка при изменении режима")
    
    return redirect('core:teen_dashboard')

# ==============================================================================
# AI AUTOMATION VIEWS (Originally from views_automation.py)
# ==============================================================================

@login_required
def import_data_view(request):
    """
    Advanced data import with AI-powered mapping
    """
    return render(request, 'automation/import.html', {'user': request.user})

@login_required
def review_transactions_view(request):
    """
    UI for reviewing and confirming AI-categorized transactions
    """
    return render(request, 'automation/review.html', {'user': request.user})

@login_required
def ai_insights_view(request):
    """
    Dashboard for deep AI financial insights
    """
    return render(request, 'automation/insights.html', {'user': request.user})


# ==============================================================================
# NEW: AI ACCOUNTANT API ENDPOINTS
# ==============================================================================

@csrf_exempt
@login_required
def import_text_api(request):
    """
    Import transactions from plain text
    POST: {text: str, auto_categorize: bool}
    """
    if request.method == 'POST':
        try:
            from core.services.import_service import ImportService
            
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            auto_categorize = data.get('auto_categorize', True)
            
            if not text:
                return JsonResponse({'error': 'Текст не может быть пустым'}, status=400)
            
            import_service = ImportService(request.user)
            result = import_service.import_from_text(text, auto_categorize)
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Text import error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


@login_required
def review_queue_api(request):
    """
    Get transactions that need review
    """
    try:
        from core.services.import_service import ImportService
        
        import_service = ImportService(request.user)
        queue = import_service.get_review_queue()
        
        # Serialize and Combine
        transactions = []
        
        for inc in queue['incomes']:
            transactions.append({
                'id': inc.id,
                'type': 'income',
                'date': inc.date.isoformat(),
                'amount': float(inc.amount),
                'category': inc.income_type,
                'category_display': inc.get_income_type_display() if hasattr(inc, 'get_income_type_display') else inc.income_type,
                'description': inc.description or '',
                'merchant': inc.merchant or 'Неизвестно',
                'needs_review': inc.needs_review,
                'confidence': inc.ai_category_confidence or 0.5
            })
            
        for exp in queue['expenses']:
            transactions.append({
                'id': exp.id,
                'type': 'expense',
                'date': exp.date.isoformat(),
                'amount': float(exp.amount),
                'category': exp.expense_type,
                'category_display': exp.get_expense_type_display() if hasattr(exp, 'get_expense_type_display') else exp.expense_type,
                'description': exp.description or '',
                'merchant': exp.merchant or 'Неизвестно',
                'needs_review': exp.needs_review,
                'confidence': exp.ai_category_confidence or 0.5
            })
            
        # Sort by date descending
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return JsonResponse({
            'transactions': transactions,
            'total': queue['total']
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Review queue error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def update_category_api(request):
    """
    Update transaction category, confirm, or delete transaction.
    POST: {
        transaction_id: int, 
        transaction_type: str, 
        category: str (optional),
        confirm: bool (optional),
        delete: bool (optional)
    }
    """
    if request.method == 'POST':
        try:
            import json
            from core.models import Income, Expense
            
            data = json.loads(request.body)
            transaction_id = data.get('transaction_id')
            transaction_type = data.get('transaction_type')
            category = data.get('category')
            confirm = data.get('confirm', False)
            delete_action = data.get('delete', False)
            
            if not transaction_id or not transaction_type:
                return JsonResponse({'error': 'Недостаточно данных'}, status=400)
            
            # Select model
            model = Income if transaction_type == 'income' else Expense
            
            try:
                tx = model.objects.get(id=transaction_id, user=request.user)
            except model.DoesNotExist:
                return JsonResponse({'error': 'Транзакция не найдена'}, status=404)

            # Handle Delete
            if delete_action:
                tx.delete()
                return JsonResponse({'success': True, 'message': 'Транзакция удалена'})

            # Handle Category Update
            if category:
                tx.category = category
                # Auto-confirm if category is manually set? Optional. 
                # For now let's just set the category.
                if confirm:
                     tx.needs_review = False
                tx.save()
                return JsonResponse({'success': True, 'message': 'Категория обновлена'})

            # Handle Confirm only
            if confirm:
                tx.needs_review = False
                tx.save()
                return JsonResponse({'success': True, 'message': 'Транзакция подтверждена'})
            
            return JsonResponse({'error': 'Нет действий для выполнения'}, status=400)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Update category error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


@login_required
def forecast_api(request):
    """
    Get financial forecast
    """
    try:
        from core.services.forecasting import ForecastingService
        
        forecasting = ForecastingService(request.user)
        
        # Get historical summary
        historical = forecasting.get_historical_summary(months=6)
        
        # Get next month forecast
        next_month = forecasting.forecast_next_month()
        
        # Get category forecasts
        expense_forecast = forecasting.forecast_by_category('expense', months=3)
        income_forecast = forecasting.forecast_by_category('income', months=3)
        
        # Get money leaks
        money_leaks = forecasting.identify_money_leaks(top_n=5)
        
        return JsonResponse({
            'historical': {
                'months_analyzed': historical['months_analyzed'],
                'avg_monthly_income': float(historical['avg_monthly_income']),
                'avg_monthly_expense': float(historical['avg_monthly_expense']),
                'avg_monthly_net': float(historical['avg_monthly_net']),
                'income_stability': historical['income_stability'],
                'expense_stability': historical['expense_stability'],
            },
            'next_month': {
                'predicted_income': float(next_month['predicted_income']),
                'predicted_expense': float(next_month['predicted_expense']),
                'predicted_net': float(next_month['predicted_net']),
                'confidence': next_month['confidence'],
                'method': next_month['method']
            },
            'category_forecast': {
                'expenses': {k: float(v) for k, v in expense_forecast.items()},
                'incomes': {k: float(v) for k, v in income_forecast.items()}
            },
            'money_leaks': money_leaks
        })
        
    except Exception as e:
        logger.error(f"Forecast API error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def goal_prediction_api(request, goal_id):
    """
    Get goal achievement prediction
    """
    try:
        from core.services.forecasting import ForecastingService
        
        goal = get_object_or_404(UserGoal, id=goal_id, user=request.user)
        forecasting = ForecastingService(request.user)
        
        prediction = forecasting.predict_goal_achievement(goal)
        
        return JsonResponse({
            'goal_id': goal.id,
            'goal_title': goal.title,
            'probability': prediction['probability'],
            'on_track': prediction['on_track'],
            'required_monthly_saving': float(prediction['required_monthly_saving']),
            'current_monthly_saving': float(prediction['current_monthly_saving']),
            'recommendation': prediction['recommendation']
        })
        
    except Exception as e:
        logger.error(f"Goal prediction error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def monthly_advice_api(request):
    """
    Get AI-generated monthly financial advice
    """
    try:
        from core.services.ai_advisor import AIAdvisorService
        
        advisor = AIAdvisorService(request.user)
        advice_data = advisor.generate_monthly_advice()
        
        return JsonResponse({
            'summary': advice_data['summary'],
            'advice': advice_data['advice'],
            'action_items': advice_data['action_items'],
            'highlights': {
                'monthly_net': float(advice_data['highlights']['monthly_net']),
                'top_leak': advice_data['highlights']['top_leak'],
                'goals_count': advice_data['highlights']['goals_count']
            },
            'confidence': advice_data['confidence']
        })
        
    except Exception as e:
        logger.error(f"Monthly advice error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def spending_analysis_api(request):
    """
    Get detailed spending pattern analysis
    """
    try:
        from core.services.ai_advisor import AIAdvisorService
        
        advisor = AIAdvisorService(request.user)
        patterns = advisor.analyze_spending_patterns()
        
        return JsonResponse({
            'total_expense': float(patterns['total_expense']),
            'essential_expense': float(patterns['essential_expense']),
            'non_essential_expense': float(patterns['non_essential_expense']),
            'essential_percentage': patterns['essential_percentage'],
            'top_categories': {k: float(v) for k, v in patterns['top_categories'].items()}
        })
        
    except Exception as e:
        logger.error(f"Spending analysis error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def auto_update_goals_api(request):
    """
    Automatically update goal progress based on transactions
    """
    try:
        from decimal import Decimal
        from datetime import timedelta
        
        goals = UserGoal.objects.filter(user=request.user, status='active')
        updated_count = 0
        
        for goal in goals:
            # Find transactions linked to this goal's category
            # For now, we'll calculate based on net savings
            
            # Get transactions since goal creation
            incomes = Income.objects.filter(
                user=request.user,
                date__gte=goal.created_at.date()
            ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
            
            expenses = Expense.objects.filter(
                user=request.user,
                date__gte=goal.created_at.date()
            ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
            
            # Calculate net savings
            net_savings = incomes - expenses
            
            # Update goal if positive savings
            if net_savings > 0:
                # Allocate a portion to this goal (e.g., 30% of net savings)
                allocation_rate = Decimal('0.3')
                allocated_amount = net_savings * allocation_rate
                
                goal.current_amount = min(allocated_amount, goal.target_amount)
                goal.save()
                updated_count += 1
        
        return JsonResponse({
            'success': True,
            'updated_count': updated_count,
            'message': f'Обновлено {updated_count} целей'
        })
        
    except Exception as e:
        logger.error(f"Auto update goals error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


