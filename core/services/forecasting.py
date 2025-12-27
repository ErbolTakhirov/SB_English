"""
Forecasting Service for SB Finance AI
Analyzes historical data and predicts future financial trends
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from collections import defaultdict
from django.db.models import Sum, Avg, Count, Q
from django.contrib.auth.models import User

from core.models import Income, Expense, UserGoal

logger = logging.getLogger(__name__)


class ForecastingService:
    """
    Analyzes 3-12 months of history and generates forecasts
    """
    
    def __init__(self, user: User):
        self.user = user
    
    def get_historical_summary(self, months: int = 6) -> Dict:
        """
        Get summary of last N months
        Returns: {
            'months_analyzed': int,
            'avg_monthly_income': Decimal,
            'avg_monthly_expense': Decimal,
            'avg_monthly_net': Decimal,
            'total_transactions': int,
            'income_stability': float,  # 0-1, higher is more stable
            'expense_stability': float,
        }
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get transactions
        incomes = Income.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
        expenses = Expense.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
        
        # Calculate monthly aggregates
        monthly_income = defaultdict(Decimal)
        monthly_expense = defaultdict(Decimal)
        
        for inc in incomes:
            month_key = inc.date.strftime('%Y-%m')
            monthly_income[month_key] += inc.amount
        
        for exp in expenses:
            month_key = exp.date.strftime('%Y-%m')
            monthly_expense[month_key] += exp.amount
        
        # Calculate averages
        income_values = list(monthly_income.values()) if monthly_income else [Decimal(0)]
        expense_values = list(monthly_expense.values()) if monthly_expense else [Decimal(0)]
        
        avg_income = sum(income_values) / len(income_values) if income_values else Decimal(0)
        avg_expense = sum(expense_values) / len(expense_values) if expense_values else Decimal(0)
        
        # Calculate stability (coefficient of variation)
        income_stability = self._calculate_stability(income_values)
        expense_stability = self._calculate_stability(expense_values)
        
        return {
            'months_analyzed': len(set(list(monthly_income.keys()) + list(monthly_expense.keys()))),
            'avg_monthly_income': round(avg_income, 2),
            'avg_monthly_expense': round(avg_expense, 2),
            'avg_monthly_net': round(avg_income - avg_expense, 2),
            'total_transactions': incomes.count() + expenses.count(),
            'income_stability': income_stability,
            'expense_stability': expense_stability,
        }
    
    def forecast_next_month(self) -> Dict:
        """
        Forecast next month's income, expenses, and net
        Returns: {
            'predicted_income': Decimal,
            'predicted_expense': Decimal,
            'predicted_net': Decimal,
            'confidence': float,  # 0-1
            'method': str,  # 'historical_average', 'trend_analysis', etc.
        }
        """
        summary = self.get_historical_summary(months=6)
        
        # Simple method: use historical average
        # TODO: Implement trend analysis for better predictions
        
        confidence = 0.7
        if summary['months_analyzed'] < 3:
            confidence = 0.4
        elif summary['months_analyzed'] >= 6:
            confidence = 0.8
        
        # Adjust confidence based on stability
        confidence *= (summary['income_stability'] + summary['expense_stability']) / 2
        
        return {
            'predicted_income': summary['avg_monthly_income'],
            'predicted_expense': summary['avg_monthly_expense'],
            'predicted_net': summary['avg_monthly_net'],
            'confidence': round(confidence, 2),
            'method': 'historical_average'
        }
    
    def forecast_by_category(self, transaction_type: str = 'expense', months: int = 3) -> Dict[str, Decimal]:
        """
        Forecast spending/income by category
        Returns: {'category': predicted_amount, ...}
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        if transaction_type == 'income':
            transactions = Income.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
            category_field = 'income_type'
        else:
            transactions = Expense.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
            category_field = 'expense_type'
        
        # Group by category
        category_totals = transactions.values(category_field).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Calculate monthly average per category
        forecasts = {}
        for item in category_totals:
            category = item[category_field]
            total = item['total']
            monthly_avg = total / max(months, 1)
            forecasts[category] = round(monthly_avg, 2)
        
        return forecasts
    
    def predict_goal_achievement(self, goal: UserGoal) -> Dict:
        """
        Predict probability of achieving a goal
        Returns: {
            'probability': float,  # 0-1
            'on_track': bool,
            'required_monthly_saving': Decimal,
            'current_monthly_saving': Decimal,
            'recommendation': str,
        }
        """
        # Calculate required monthly saving
        remaining = goal.target_amount - goal.current_amount
        days_left = goal.days_remaining()
        
        if days_left <= 0:
            return {
                'probability': 0.0 if remaining > 0 else 1.0,
                'on_track': False,
                'required_monthly_saving': Decimal(0),
                'current_monthly_saving': Decimal(0),
                'recommendation': 'Срок истек. Установите новую дату или увеличьте текущую сумму.'
            }
        
        months_left = max(days_left / 30, 0.5)
        required_monthly = remaining / Decimal(months_left)
        
        # Get current saving rate
        forecast = self.forecast_next_month()
        current_monthly_net = forecast['predicted_net']
        
        # Calculate probability
        if current_monthly_net <= 0:
            probability = 0.1
            on_track = False
            recommendation = f"Ваши расходы превышают доходы. Сократите траты на {abs(current_monthly_net):.0f} в месяц."
        elif current_monthly_net >= required_monthly:
            probability = 0.9
            on_track = True
            recommendation = f"Отлично! Вы на правильном пути. Продолжайте откладывать {required_monthly:.0f} в месяц."
        else:
            # Partial probability
            probability = float(current_monthly_net / required_monthly) * 0.7
            on_track = False
            gap = required_monthly - current_monthly_net
            recommendation = f"Нужно откладывать еще {gap:.0f} в месяц. Попробуйте сократить необязательные траты."
        
        return {
            'probability': round(probability, 2),
            'on_track': on_track,
            'required_monthly_saving': round(required_monthly, 2),
            'current_monthly_saving': round(current_monthly_net, 2),
            'recommendation': recommendation
        }
    
    def identify_money_leaks(self, top_n: int = 3) -> List[Dict]:
        """
        Identify top spending categories (money leaks)
        Returns: [{'category': str, 'amount': Decimal, 'percentage': float}, ...]
        """
        # Last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        expenses = Expense.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
        
        total_expense = expenses.aggregate(total=Sum('amount'))['total'] or Decimal(0)
        
        category_totals = expenses.values('expense_type').annotate(
            total=Sum('amount')
        ).order_by('-total')[:top_n]
        
        leaks = []
        for item in category_totals:
            percentage = (item['total'] / total_expense * 100) if total_expense > 0 else 0
            leaks.append({
                'category': item['expense_type'],
                'amount': round(item['total'], 2),
                'percentage': round(percentage, 1)
            })
        
        return leaks
    
    def _calculate_stability(self, values: List[Decimal]) -> float:
        """
        Calculate stability score (0-1, higher is more stable)
        Uses inverse of coefficient of variation
        """
        if not values or len(values) < 2:
            return 0.5
        
        # Convert to float for mathematical operations
        float_values = [float(v) for v in values]
        
        mean = sum(float_values) / len(float_values)
        if mean == 0:
            return 0.5
        
        variance = sum((x - mean) ** 2 for x in float_values) / len(float_values)
        std_dev = variance ** 0.5
        
        # Coefficient of variation
        cv = std_dev / mean if mean > 0 else 1.0
        
        # Convert to stability score (inverse)
        stability = 1 / (1 + cv)
        
        return round(stability, 2)
