"""
AI Advisor Service for SB Finance AI
Generates personalized financial advice for young adults
"""

import logging
from typing import Dict, List, Optional
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User

from core.ai_services.llm_manager import llm_manager
from core.services.forecasting import ForecastingService
from core.models import UserGoal, Income, Expense

logger = logging.getLogger(__name__)


class AIAdvisorService:
    """
    Generates personalized financial advice based on user data
    """
    
    def __init__(self, user: User):
        self.user = user
        self.forecasting = ForecastingService(user)
    
    def generate_monthly_advice(self, month: Optional[date] = None) -> Dict:
        """
        Generate comprehensive monthly financial advice
        Returns: {
            'summary': str,
            'advice': str,
            'action_items': List[str],
            'highlights': Dict,
            'confidence': float
        }
        """
        if month is None:
            month = date.today()
        
        # Gather data
        historical = self.forecasting.get_historical_summary(months=6)
        forecast = self.forecasting.forecast_next_month()
        money_leaks = self.forecasting.identify_money_leaks(top_n=3)
        goals = UserGoal.objects.filter(user=self.user, status='active')
        
        # Build context for AI
        context = self._build_context(historical, forecast, money_leaks, goals)
        
        # Generate advice using AI or fallback
        if hasattr(llm_manager, 'current_provider'):
            advice_data = self._generate_ai_advice(context)
        else:
            advice_data = self._generate_rule_based_advice(context)
        
        return advice_data
    
    def generate_goal_advice(self, goal: UserGoal) -> str:
        """
        Generate specific advice for achieving a goal
        """
        prediction = self.forecasting.predict_goal_achievement(goal)
        
        if prediction['on_track']:
            return f"🎯 Отлично! Вы на пути к достижению цели '{goal.title}'. {prediction['recommendation']}"
        else:
            return f"⚠️ Для достижения цели '{goal.title}' нужно скорректировать план. {prediction['recommendation']}"
    
    def analyze_spending_patterns(self) -> Dict:
        """
        Analyze spending patterns and provide insights
        """
        # Last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        expenses = Expense.objects.filter(user=self.user, date__gte=start_date, date__lte=end_date)
        
        # Calculate patterns
        total_expense = sum(e.amount for e in expenses)
        essential_expense = sum(e.amount for e in expenses if e.is_essential)
        non_essential = total_expense - essential_expense
        
        # Category breakdown
        category_forecast = self.forecasting.forecast_by_category('expense', months=3)
        
        return {
            'total_expense': round(total_expense, 2),
            'essential_expense': round(essential_expense, 2),
            'non_essential_expense': round(non_essential, 2),
            'essential_percentage': round((essential_expense / total_expense * 100) if total_expense > 0 else 0, 1),
            'top_categories': category_forecast,
        }
    
    def _build_context(self, historical: Dict, forecast: Dict, 
                      money_leaks: List[Dict], goals) -> Dict:
        """Build context dictionary for AI"""
        return {
            'historical': historical,
            'forecast': forecast,
            'money_leaks': money_leaks,
            'goals': [
                {
                    'title': g.title,
                    'target': float(g.target_amount),
                    'current': float(g.current_amount),
                    'progress': g.progress_percentage(),
                    'days_left': g.days_remaining()
                }
                for g in goals
            ],
            'spending_patterns': self.analyze_spending_patterns()
        }
    
    def _generate_ai_advice(self, context: Dict) -> Dict:
        """Generate advice using LLM"""
        # Build prompt for young adults
        prompt = f"""Ты финансовый советник для молодых людей (18-25 лет). 
Проанализируй финансовую ситуацию и дай конкретные, понятные советы.

📊 Финансовая ситуация:
- Средний месячный доход: {context['historical']['avg_monthly_income']} сом
- Средний месячный расход: {context['historical']['avg_monthly_expense']} сом
- Чистый доход: {context['historical']['avg_monthly_net']} сом
- Стабильность доходов: {context['historical']['income_stability'] * 100:.0f}%
- Стабильность расходов: {context['historical']['expense_stability'] * 100:.0f}%

💸 Основные траты (утечки денег):
{chr(10).join([f"- {leak['category']}: {leak['amount']} сом ({leak['percentage']}%)" for leak in context['money_leaks']])}

🎯 Активные цели:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} сом ({g['progress']:.0f}%), осталось {g['days_left']} дней" for g in context['goals']]) if context['goals'] else "Нет активных целей"}

📈 Прогноз на следующий месяц:
- Ожидаемый доход: {context['forecast']['predicted_income']} сом
- Ожидаемый расход: {context['forecast']['predicted_expense']} сом
- Уверенность прогноза: {context['forecast']['confidence'] * 100:.0f}%

Дай совет в формате:
1. **Краткая сводка** (2-3 предложения о текущей ситуации)
2. **Главный совет** (что важнее всего сделать прямо сейчас)
3. **Конкретные действия** (3-5 пунктов, что делать)

Пиши простым языком, как друг. Используй эмодзи. Будь конкретным и мотивирующим."""

        try:
            messages = [
                {"role": "system", "content": "Ты дружелюбный финансовый коуч для молодежи. Говори просто и конкретно."},
                {"role": "user", "content": prompt}
            ]
            
            # Use sync method instead of async
            response = llm_manager.chat_sync(messages, temperature=0.7, max_tokens=800)
            
            # Parse response
            advice_text = response.content
            
            # Extract action items (lines starting with numbers or bullets)
            import re
            action_items = re.findall(r'(?:^|\n)[\d\-\*•]\s*(.+?)(?=\n|$)', advice_text)
            
            return {
                'summary': self._extract_summary(advice_text),
                'advice': advice_text,
                'action_items': action_items[:5] if action_items else [],
                'highlights': {
                    'monthly_net': context['historical']['avg_monthly_net'],
                    'top_leak': context['money_leaks'][0] if context['money_leaks'] else None,
                    'goals_count': len(context['goals'])
                },
                'confidence': context['forecast']['confidence']
            }
            
        except Exception as e:
            logger.error(f"AI advice generation error: {e}")
            return self._generate_rule_based_advice(context)
    
    def _generate_rule_based_advice(self, context: Dict) -> Dict:
        """Fallback rule-based advice"""
        monthly_net = context['historical']['avg_monthly_net']
        
        # Generate summary
        if monthly_net > 0:
            summary = f"💰 Хорошие новости! В среднем вы откладываете {monthly_net:.0f} сом в месяц."
        elif monthly_net < 0:
            summary = f"⚠️ Внимание! Ваши расходы превышают доходы на {abs(monthly_net):.0f} сом в месяц."
        else:
            summary = "📊 Ваши доходы и расходы примерно равны. Пора начать откладывать!"
        
        # Generate action items
        action_items = []
        
        # Check money leaks
        if context['money_leaks']:
            top_leak = context['money_leaks'][0]
            action_items.append(f"Сократите траты на {top_leak['category']} - это {top_leak['percentage']}% ваших расходов")
        
        # Check goals
        if context['goals']:
            action_items.append(f"Работайте над {len(context['goals'])} активными целями")
        else:
            action_items.append("Поставьте финансовую цель - это мотивирует экономить")
        
        # Savings advice
        if monthly_net > 0:
            action_items.append(f"Откладывайте {monthly_net * Decimal('0.8'):.0f} сом ежемесячно на цели")
        else:
            action_items.append("Найдите 1-2 категории расходов, которые можно сократить на 20%")
        
        # Income advice
        if context['historical']['income_stability'] < 0.7:
            action_items.append("Ищите дополнительные источники дохода для стабильности")
        
        advice_text = f"{summary}\n\n**Рекомендации:**\n" + "\n".join([f"{i+1}. {item}" for i, item in enumerate(action_items)])
        
        return {
            'summary': summary,
            'advice': advice_text,
            'action_items': action_items,
            'highlights': {
                'monthly_net': monthly_net,
                'top_leak': context['money_leaks'][0] if context['money_leaks'] else None,
                'goals_count': len(context['goals'])
            },
            'confidence': 0.6
        }
    
    def _extract_summary(self, text: str) -> str:
        """Extract first paragraph as summary"""
        paragraphs = text.split('\n\n')
        if paragraphs:
            # Remove markdown headers
            summary = paragraphs[0].replace('#', '').strip()
            return summary[:200]
        return text[:200]
