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
            return f"🎯 Great job! You are on track to achieve '{goal.title}'. {prediction['recommendation']}"
        else:
            return f"⚠️ To achieve '{goal.title}', you need to adjust your plan. {prediction['recommendation']}"
    
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
        prompt = f"""You are a financial advisor for young adults (18-25 years old). 
Analyze the financial situation and give specific, clear advice.

📊 Financial Situation:
- Avg Monthly Income: {context['historical']['avg_monthly_income']} KGS
- Avg Monthly Expense: {context['historical']['avg_monthly_expense']} KGS
- Net Income: {context['historical']['avg_monthly_net']} KGS
- Income Stability: {context['historical']['income_stability'] * 100:.0f}%
- Expense Stability: {context['historical']['expense_stability'] * 100:.0f}%

💸 Money Leaks (Top Expenses):
{chr(10).join([f"- {leak['category']}: {leak['amount']} KGS ({leak['percentage']}%)" for leak in context['money_leaks']])}

🎯 Active Goals:
{chr(10).join([f"- {g['title']}: {g['current']}/{g['target']} KGS ({g['progress']:.0f}%), {g['days_left']} days left" for g in context['goals']]) if context['goals'] else "No active goals"}

📈 Next Month Forecast:
- Expected Income: {context['forecast']['predicted_income']} KGS
- Expected Expense: {context['forecast']['predicted_expense']} KGS
- Forecast Confidence: {context['forecast']['confidence'] * 100:.0f}%

Provide advice in the following format:
1. **Summary** (2-3 sentences about current situation)
2. **Main Advice** (what is most important to do right now)
3. **Action Items** (3-5 specific bullet points)

Write in simple language, like a friend. Use emojis. Be specific and motivating. Respond in English."""

        try:
            messages = [
                {"role": "system", "content": "You are a friendly financial coach for youth. Speak simply and concretely. Response in English."},
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
            summary = f"💰 Good news! On average, you save {monthly_net:.0f} KGS/mo."
        elif monthly_net < 0:
            summary = f"⚠️ Attention! Your expenses exceed income by {abs(monthly_net):.0f} KGS/mo."
        else:
            summary = "📊 Your income and expenses are equal. Time to start saving!"
        
        # Generate action items
        action_items = []
        
        # Check money leaks
        if context['money_leaks']:
            top_leak = context['money_leaks'][0]
            action_items.append(f"Cut spending on {top_leak['category']} - it's {top_leak['percentage']}% of your expenses")
        
        # Check goals
        if context['goals']:
            action_items.append(f"Work on your {len(context['goals'])} active goals")
        else:
            action_items.append("Set a financial goal - it motivates saving")
        
        # Savings advice
        if monthly_net > 0:
            action_items.append(f"Save {monthly_net * Decimal('0.8'):.0f} KGS monthly for goals")
        else:
            action_items.append("Find 1-2 expense categories to cut by 20%")
        
        # Income advice
        if context['historical']['income_stability'] < 0.7:
            action_items.append("Look for additional income sources for stability")
        
        advice_text = f"{summary}\n\n**Recommendations:**\n" + "\n".join([f"{i+1}. {item}" for i, item in enumerate(action_items)])
        
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
