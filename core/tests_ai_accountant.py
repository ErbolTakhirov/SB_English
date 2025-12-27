"""
Test suite for AI Accountant Services
Run with: python manage.py test core.tests_ai_accountant
"""

from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal

from core.models import Income, Expense, UserGoal
from core.services.text_parser import text_parser
from core.services.categorization import categorization_service
from core.services.import_service import ImportService
from core.services.forecasting import ForecastingService
from core.services.ai_advisor import AIAdvisorService


class TextParserTests(TestCase):
    """Test text parsing functionality"""
    
    def test_parse_simple_transaction(self):
        """Test parsing a simple transaction"""
        text = "01.12.2024 Магнит 450р"
        result = text_parser.parse_text(text)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['amount'], Decimal('450'))
        self.assertEqual(result[0]['merchant'], 'Магнит')
        self.assertFalse(result[0]['needs_review'])
    
    def test_parse_multiple_transactions(self):
        """Test parsing multiple transactions"""
        text = """01.12 Магнит 450р
02.12 Яндекс.Такси 320р
03.12 Зарплата 50000с"""
        
        result = text_parser.parse_text(text)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['amount'], Decimal('450'))
        self.assertEqual(result[1]['amount'], Decimal('320'))
        self.assertEqual(result[2]['amount'], Decimal('50000'))
    
    def test_parse_different_date_formats(self):
        """Test parsing different date formats"""
        text = """01.12.2024 Shop1 100
2024-12-02 Shop2 200
12/03/2024 Shop3 300"""
        
        result = text_parser.parse_text(text)
        
        self.assertEqual(len(result), 3)
        self.assertIsNotNone(result[0]['date'])
        self.assertIsNotNone(result[1]['date'])
        self.assertIsNotNone(result[2]['date'])
    
    def test_parse_different_currencies(self):
        """Test parsing different currencies"""
        text = """01.12 Shop1 100р
02.12 Shop2 200$
03.12 Shop3 300сом"""
        
        result = text_parser.parse_text(text)
        
        self.assertEqual(result[0]['currency'], 'RUB')
        self.assertEqual(result[1]['currency'], 'USD')
        self.assertEqual(result[2]['currency'], 'KGS')


class CategorizationServiceTests(TestCase):
    """Test categorization service"""
    
    def test_rule_based_categorization_expense(self):
        """Test rule-based expense categorization"""
        transactions = [
            {'description': 'Магнит продукты', 'merchant': 'Магнит', 'amount': 450},
            {'description': 'Яндекс такси', 'merchant': 'Яндекс', 'amount': 320},
        ]
        
        categories = categorization_service._categorize_with_rules(transactions, 'expense')
        
        self.assertEqual(categories[0], 'food')
        self.assertEqual(categories[1], 'transport')
    
    def test_rule_based_categorization_income(self):
        """Test rule-based income categorization"""
        transactions = [
            {'description': 'Зарплата', 'merchant': 'Компания', 'amount': 50000},
            {'description': 'Подарок от родителей', 'merchant': '', 'amount': 5000},
        ]
        
        categories = categorization_service._categorize_with_rules(transactions, 'income')
        
        self.assertEqual(categories[0], 'salary')
        self.assertEqual(categories[1], 'gift')
    
    def test_learn_from_correction(self):
        """Test learning from user corrections"""
        categorization_service.learn_from_correction('Starbucks', 'food')
        
        # Check if learned
        self.assertIn('starbucks', categorization_service.user_corrections)
        self.assertEqual(categorization_service.user_corrections['starbucks'], 'food')


class ImportServiceTests(TestCase):
    """Test import service"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.import_service = ImportService(self.user)
    
    def test_import_from_text(self):
        """Test importing from text"""
        text = """01.12.2024 Магнит 450р
02.12.2024 Зарплата 50000с"""
        
        result = self.import_service.import_from_text(text, auto_categorize=False)
        
        self.assertTrue(result['success'])
        self.assertGreater(result['incomes_created'] + result['expenses_created'], 0)
    
    def test_get_review_queue(self):
        """Test getting review queue"""
        # Create transaction needing review
        Income.objects.create(
            user=self.user,
            amount=1000,
            date=date.today(),
            income_type='other',
            needs_review=True
        )
        
        queue = self.import_service.get_review_queue()
        
        self.assertGreater(queue['total'], 0)
    
    def test_update_transaction_category(self):
        """Test updating transaction category"""
        income = Income.objects.create(
            user=self.user,
            amount=1000,
            date=date.today(),
            income_type='other',
            needs_review=True
        )
        
        success = self.import_service.update_transaction_category(
            income.id, 'income', 'salary'
        )
        
        self.assertTrue(success)
        
        # Verify update
        income.refresh_from_db()
        self.assertEqual(income.income_type, 'salary')
        self.assertFalse(income.needs_review)


class ForecastingServiceTests(TestCase):
    """Test forecasting service"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.forecasting = ForecastingService(self.user)
        
        # Create sample data
        for i in range(6):
            month_date = date.today() - timedelta(days=30 * i)
            
            Income.objects.create(
                user=self.user,
                amount=50000,
                date=month_date,
                income_type='salary'
            )
            
            Expense.objects.create(
                user=self.user,
                amount=35000,
                date=month_date,
                expense_type='food'
            )
    
    def test_get_historical_summary(self):
        """Test getting historical summary"""
        summary = self.forecasting.get_historical_summary(months=6)
        
        self.assertGreater(summary['months_analyzed'], 0)
        self.assertGreater(summary['avg_monthly_income'], 0)
        self.assertGreater(summary['avg_monthly_expense'], 0)
        self.assertGreater(summary['avg_monthly_net'], 0)
    
    def test_forecast_next_month(self):
        """Test forecasting next month"""
        forecast = self.forecasting.forecast_next_month()
        
        self.assertIn('predicted_income', forecast)
        self.assertIn('predicted_expense', forecast)
        self.assertIn('predicted_net', forecast)
        self.assertIn('confidence', forecast)
        self.assertGreater(forecast['confidence'], 0)
    
    def test_forecast_by_category(self):
        """Test forecasting by category"""
        forecast = self.forecasting.forecast_by_category('expense', months=3)
        
        self.assertIn('food', forecast)
        self.assertGreater(forecast['food'], 0)
    
    def test_identify_money_leaks(self):
        """Test identifying money leaks"""
        leaks = self.forecasting.identify_money_leaks(top_n=3)
        
        self.assertGreater(len(leaks), 0)
        self.assertIn('category', leaks[0])
        self.assertIn('amount', leaks[0])
        self.assertIn('percentage', leaks[0])
    
    def test_predict_goal_achievement(self):
        """Test predicting goal achievement"""
        goal = UserGoal.objects.create(
            user=self.user,
            title='Test Goal',
            target_amount=100000,
            current_amount=50000,
            category='electronics',
            target_date=date.today() + timedelta(days=180)
        )
        
        prediction = self.forecasting.predict_goal_achievement(goal)
        
        self.assertIn('probability', prediction)
        self.assertIn('on_track', prediction)
        self.assertIn('required_monthly_saving', prediction)
        self.assertIn('recommendation', prediction)


class AIAdvisorServiceTests(TestCase):
    """Test AI advisor service"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.advisor = AIAdvisorService(self.user)
        
        # Create sample data
        Income.objects.create(
            user=self.user,
            amount=50000,
            date=date.today(),
            income_type='salary'
        )
        
        Expense.objects.create(
            user=self.user,
            amount=35000,
            date=date.today(),
            expense_type='food'
        )
    
    def test_analyze_spending_patterns(self):
        """Test analyzing spending patterns"""
        patterns = self.advisor.analyze_spending_patterns()
        
        self.assertIn('total_expense', patterns)
        self.assertIn('essential_expense', patterns)
        self.assertIn('non_essential_expense', patterns)
        self.assertIn('essential_percentage', patterns)
    
    def test_generate_monthly_advice(self):
        """Test generating monthly advice"""
        advice = self.advisor.generate_monthly_advice()
        
        self.assertIn('summary', advice)
        self.assertIn('advice', advice)
        self.assertIn('action_items', advice)
        self.assertIn('highlights', advice)
        self.assertIn('confidence', advice)
        
        # Verify advice is not empty
        self.assertGreater(len(advice['summary']), 0)
        self.assertGreater(len(advice['advice']), 0)
    
    def test_generate_goal_advice(self):
        """Test generating goal-specific advice"""
        goal = UserGoal.objects.create(
            user=self.user,
            title='Test Goal',
            target_amount=100000,
            current_amount=50000,
            category='electronics',
            target_date=date.today() + timedelta(days=180)
        )
        
        advice = self.advisor.generate_goal_advice(goal)
        
        self.assertIsInstance(advice, str)
        self.assertGreater(len(advice), 0)


# Run tests with:
# python manage.py test core.tests_ai_accountant
