"""
Unified Import Service for SB Finance AI
Handles all types of financial data import with automatic categorization
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.db import transaction

from core.models import Income, Expense, UploadedFile
from core.services.text_parser import text_parser
from core.services.categorization import categorization_service
from core.utils.file_ingest import import_csv_transactions, import_excel_transactions

logger = logging.getLogger(__name__)


class ImportService:
    """
    Unified service for importing financial data from various sources
    """
    
    def __init__(self, user: User):
        self.user = user
    
    def import_from_text(self, text: str, auto_categorize: bool = True) -> Dict:
        """
        Import transactions from plain text
        Returns: {
            'success': bool,
            'incomes_created': int,
            'expenses_created': int,
            'needs_review': int,
            'transactions': List[Dict],
            'errors': List[str]
        }
        """
        # Parse text
        parsed_transactions = text_parser.parse_text(text)
        
        if not parsed_transactions:
            return {
                'success': False,
                'incomes_created': 0,
                'expenses_created': 0,
                'needs_review': 0,
                'transactions': [],
                'errors': ['Не удалось распознать транзакции в тексте']
            }
        
        # Categorize and save
        result = self._process_parsed_transactions(parsed_transactions, auto_categorize)
        
        return result
    
    def import_from_csv(self, file_obj, source_file: Optional[UploadedFile] = None) -> Dict:
        """
        Import from CSV file
        """
        try:
            num_incomes, num_expenses, errors, stats = import_csv_transactions(
                file_obj, 
                import_to_db=True, 
                user=self.user,
                source_file=source_file
            )
            
            # Auto-categorize 'other' transactions
            self._auto_categorize_others()
            
            return {
                'success': True,
                'incomes_created': num_incomes,
                'expenses_created': num_expenses,
                'needs_review': 0,
                'duplicates_found': stats.get('duplicates_found', 0),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            return {
                'success': False,
                'incomes_created': 0,
                'expenses_created': 0,
                'needs_review': 0,
                'errors': [str(e)]
            }
    
    def import_from_excel(self, file_obj, source_file: Optional[UploadedFile] = None) -> Dict:
        """
        Import from Excel file
        """
        try:
            num_incomes, num_expenses, errors, stats = import_excel_transactions(
                file_obj,
                import_to_db=True,
                user=self.user,
                source_file=source_file
            )
            
            # Auto-categorize 'other' transactions
            self._auto_categorize_others()
            
            return {
                'success': True,
                'incomes_created': num_incomes,
                'expenses_created': num_expenses,
                'needs_review': 0,
                'duplicates_found': stats.get('duplicates_found', 0),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Excel import error: {e}")
            return {
                'success': False,
                'incomes_created': 0,
                'expenses_created': 0,
                'needs_review': 0,
                'errors': [str(e)]
            }
    
    def _process_parsed_transactions(self, parsed_transactions: List[Dict], 
                                    auto_categorize: bool = True) -> Dict:
        """
        Process parsed transactions: categorize and save to DB
        """
        incomes_created = 0
        expenses_created = 0
        needs_review = 0
        errors = []
        saved_transactions = []
        
        # Separate by type (heuristic: positive amounts are income)
        income_candidates = []
        expense_candidates = []
        
        for trans in parsed_transactions:
            if trans.get('needs_review'):
                needs_review += 1
                continue
            
            # Determine type based on keywords or amount
            description = trans.get('description', '').lower()
            merchant = trans.get('merchant', '').lower()
            
            # Income keywords
            income_keywords = ['зарплата', 'salary', 'доход', 'income', 'подарок', 'gift', 
                             'карманные', 'allowance', 'фриланс', 'freelance']
            
            is_income = any(kw in description or kw in merchant for kw in income_keywords)
            
            if is_income:
                income_candidates.append(trans)
            else:
                expense_candidates.append(trans)
        
        # Auto-categorize
        if auto_categorize:
            income_categories = categorization_service.categorize_batch(
                income_candidates, 'income'
            ) if income_candidates else []
            
            expense_categories = categorization_service.categorize_batch(
                expense_candidates, 'expense'
            ) if expense_candidates else []
        else:
            income_categories = ['other'] * len(income_candidates)
            expense_categories = ['other'] * len(expense_candidates)
        
        # Save to database
        with transaction.atomic():
            # Save incomes
            for trans, category in zip(income_candidates, income_categories):
                try:
                    income = Income.objects.create(
                        user=self.user,
                        amount=trans['amount'],
                        date=trans['date'],
                        income_type=category,
                        description=trans.get('description', ''),
                        merchant=trans.get('merchant', ''),
                        currency=trans.get('currency', 'KGS'),
                        needs_review=trans.get('needs_review', False),
                        ai_category_confidence=0.8 if auto_categorize else None
                    )
                    incomes_created += 1
                    saved_transactions.append({
                        'id': income.id,
                        'type': 'income',
                        'amount': float(income.amount),
                        'category': category
                    })
                except Exception as e:
                    errors.append(f"Ошибка сохранения дохода: {e}")
            
            # Save expenses
            for trans, category in zip(expense_candidates, expense_categories):
                try:
                    expense = Expense.objects.create(
                        user=self.user,
                        amount=trans['amount'],
                        date=trans['date'],
                        expense_type=category,
                        description=trans.get('description', ''),
                        merchant=trans.get('merchant', ''),
                        currency=trans.get('currency', 'KGS'),
                        needs_review=trans.get('needs_review', False),
                        ai_category_confidence=0.8 if auto_categorize else None
                    )
                    expenses_created += 1
                    saved_transactions.append({
                        'id': expense.id,
                        'type': 'expense',
                        'amount': float(expense.amount),
                        'category': category
                    })
                except Exception as e:
                    errors.append(f"Ошибка сохранения расхода: {e}")
        
        return {
            'success': True,
            'incomes_created': incomes_created,
            'expenses_created': expenses_created,
            'needs_review': needs_review,
            'transactions': saved_transactions,
            'errors': errors
        }
    
    def _auto_categorize_others(self):
        """
        Auto-categorize transactions marked as 'other'
        """
        # Get recent 'other' incomes
        other_incomes = Income.objects.filter(
            user=self.user,
            income_type='other',
            needs_review=False
        ).order_by('-created_at')[:50]
        
        if other_incomes:
            transactions = [
                {
                    'description': inc.description or '',
                    'merchant': inc.merchant or '',
                    'amount': float(inc.amount)
                }
                for inc in other_incomes
            ]
            
            categories = categorization_service.categorize_batch(transactions, 'income')
            
            for income, category in zip(other_incomes, categories):
                if category != 'other':
                    income.income_type = category
                    income.ai_category_confidence = 0.75
                    income.save(update_fields=['income_type', 'ai_category_confidence'])
        
        # Get recent 'other' expenses
        other_expenses = Expense.objects.filter(
            user=self.user,
            expense_type='other',
            needs_review=False
        ).order_by('-created_at')[:50]
        
        if other_expenses:
            transactions = [
                {
                    'description': exp.description or '',
                    'merchant': exp.merchant or '',
                    'amount': float(exp.amount)
                }
                for exp in other_expenses
            ]
            
            categories = categorization_service.categorize_batch(transactions, 'expense')
            
            for expense, category in zip(other_expenses, categories):
                if category != 'other':
                    expense.expense_type = category
                    expense.ai_category_confidence = 0.75
                    expense.save(update_fields=['expense_type', 'ai_category_confidence'])
    
    def get_review_queue(self) -> Dict:
        """
        Get transactions that need review
        Returns: {
            'incomes': List[Income],
            'expenses': List[Expense],
            'total': int
        }
        """
        incomes = Income.objects.filter(user=self.user, needs_review=True).order_by('-date')[:20]
        expenses = Expense.objects.filter(user=self.user, needs_review=True).order_by('-date')[:20]
        
        return {
            'incomes': list(incomes),
            'expenses': list(expenses),
            'total': incomes.count() + expenses.count()
        }
    
    def update_transaction_category(self, transaction_id: int, transaction_type: str, 
                                   new_category: str) -> bool:
        """
        Update transaction category and learn from correction
        """
        try:
            if transaction_type == 'income':
                transaction = Income.objects.get(id=transaction_id, user=self.user)
                transaction.income_type = new_category
                transaction.needs_review = False
                transaction.save(update_fields=['income_type', 'needs_review'])
            else:
                transaction = Expense.objects.get(id=transaction_id, user=self.user)
                transaction.expense_type = new_category
                transaction.needs_review = False
                transaction.save(update_fields=['expense_type', 'needs_review'])
            
            # Learn from correction
            merchant = transaction.merchant or ''
            if merchant:
                categorization_service.learn_from_correction(merchant, new_category)
            
            return True
        except Exception as e:
            logger.error(f"Error updating transaction category: {e}")
            return False
