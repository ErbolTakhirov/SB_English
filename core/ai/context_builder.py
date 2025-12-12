"""
Построитель обогащенного контекста для AI на основе анализа запроса.
Собирает релевантную информацию из разных источников.
"""

from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
from django.db.models import Sum, Avg, Count, Q
from collections import defaultdict

from core.models import Income, Expense, ChatMessage
from core.utils.analytics import (
    get_user_financial_memory,
    _format_currency,
    _month_key,
)


class ContextBuilder:
    """
    Строит обогащенный контекст для AI на основе типа запроса
    и приоритетов данных.
    """
    
    def __init__(self, user):
        self.user = user
        self.context = {}
    
    def build(self, query_analysis: Dict[str, Any], max_context_size: int = 10000) -> str:
        """
        Строит контекст для AI в формате markdown.
        
        Args:
            query_analysis: Результат анализа запроса
            max_context_size: Максимальный размер контекста в символах
            
        Returns:
            Markdown-форматированный контекст
        """
        priority = query_analysis.get('context_priority', ['tables', 'trends'])
        time_period = query_analysis.get('time_period', {})
        categories = query_analysis.get('categories', [])
        
        sections = []
        
        # Собираем секции в порядке приоритета
        for data_type in priority:
            if data_type == 'tables':
                section = self._build_tables_section(time_period)
            elif data_type == 'trends':
                section = self._build_trends_section(time_period)
            elif data_type == 'anomalies':
                section = self._build_anomalies_section(time_period)
            elif data_type == 'transactions':
                section = self._build_transactions_section(time_period, categories)
            elif data_type == 'goals':
                section = self._build_goals_section()
            else:
                continue
            
            if section:
                sections.append(section)
        
        # Добавляем профиль пользователя
        profile_section = self._build_user_profile_section()
        if profile_section:
            sections.insert(0, profile_section)
        
        # Объединяем все секции
        full_context = "\n\n".join(sections)
        
        # Обрезаем если слишком длинный
        if len(full_context) > max_context_size:
            full_context = full_context[:max_context_size] + "\n\n[Контекст обрезан для оптимизации]"
        
        return full_context
    
    def _build_tables_section(self, time_period: Dict[str, Any]) -> str:
        """Строит секцию с таблицами и статистикой"""
        try:
            memory = get_user_financial_memory(self.user, force_refresh=False)
            
            # Фильтруем по периоду если указан
            if time_period.get('start_date'):
                filtered_months = self._filter_months_by_period(
                    memory.get('months', {}),
                    memory.get('ordered_keys', []),
                    time_period
                )
                table = self._build_custom_table(filtered_months)
            else:
                table = memory.get('table_markdown', '')
            
            summary = memory.get('summary_text', '')
            
            return f"## 📊 Финансовая статистика\n\n{table}\n\n**Краткая сводка:** {summary}"
        except Exception as e:
            return f"## 📊 Финансовая статистика\n\n_Ошибка при загрузке статистики: {e}_"
    
    def _build_trends_section(self, time_period: Dict[str, Any]) -> str:
        """Строит секцию с трендами"""
        try:
            memory = get_user_financial_memory(self.user, force_refresh=False)
            trends = memory.get('trends', {})
            
            if not trends.get('has_enough_data'):
                return "## 📈 Тренды\n\n_Недостаточно данных для анализа трендов (требуется минимум 3 месяца)_"
            
            lines = ["## 📈 Тренды"]
            
            # Общие тренды
            income_trend = trends.get('income_trend', 'stable')
            expense_trend = trends.get('expense_trend', 'stable')
            
            trend_emoji = {
                'growth': '📈 Рост',
                'decline': '📉 Снижение',
                'stable': '➡️ Стабильность'
            }
            
            lines.append(f"\n**Общие тенденции:**")
            lines.append(f"- Доходы: {trend_emoji.get(income_trend, income_trend)}")
            lines.append(f"- Расходы: {trend_emoji.get(expense_trend, expense_trend)}")
            
            # Тренды по категориям
            cat_trends = trends.get('category_trends', {})
            if cat_trends:
                lines.append(f"\n**Тренды по категориям расходов:**")
                for cat, data in list(cat_trends.items())[:5]:
                    emoji = "📈" if data['trend'] == 'growth' else "📉" if data['trend'] == 'decline' else "➡️"
                    lines.append(
                        f"- {cat}: {emoji} {data['change_pct']:+.1f}%, "
                        f"среднее: {_format_currency(data['average'])}"
                    )
            
            return "\n".join(lines)
        except Exception as e:
            return f"## 📈 Тренды\n\n_Ошибка: {e}_"
    
    def _build_anomalies_section(self, time_period: Dict[str, Any]) -> str:
        """Строит секцию с аномалиями"""
        try:
            memory = get_user_financial_memory(self.user, force_refresh=False)
            alerts = memory.get('alerts', [])
            
            if not alerts:
                return "## 🔍 Аномалии\n\n_Аномальных транзакций не обнаружено_"
            
            lines = ["## 🔍 Аномалии и необычные траты"]
            
            for alert in alerts[:5]:  # Топ-5
                lines.append(f"- {alert.get('message', str(alert))}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"## 🔍 Аномалии\n\n_Ошибка: {e}_"
    
    def _build_transactions_section(
        self, 
        time_period: Dict[str, Any], 
        categories: List[str]
    ) -> str:
        """Строит секцию с конкретными транзакциями"""
        try:
            # Фильтруем транзакции по периоду
            query_filter = Q(user=self.user)
            
            if time_period.get('start_date'):
                query_filter &= Q(date__gte=time_period['start_date'])
            if time_period.get('end_date'):
                query_filter &= Q(date__lte=time_period['end_date'])
            
            # Фильтруем по категориям если указаны
            if categories:
                cat_filter = Q()
                for cat in categories:
                    cat_filter |= Q(category__icontains=cat)
                query_filter &= cat_filter
            
            incomes = Income.objects.filter(query_filter).order_by('-date')[:10]
            expenses = Expense.objects.filter(query_filter).order_by('-date')[:10]
            
            lines = ["## 💰 Последние транзакции"]
            
            if categories:
                lines.append(f"\n**Фильтр:** {', '.join(categories)}")
            
            if incomes.exists():
                lines.append("\n**Доходы:**")
                for inc in incomes[:5]:
                    lines.append(
                        f"- {inc.date.strftime('%d.%m.%Y')}: "
                        f"{_format_currency(inc.amount)} ({inc.category}) - {inc.description or 'без описания'}"
                    )
            
            if expenses.exists():
                lines.append("\n**Расходы:**")
                for exp in expenses[:5]:
                    lines.append(
                        f"- {exp.date.strftime('%d.%m.%Y')}: "
                        f"{_format_currency(exp.amount)} ({exp.category}) - {exp.description or 'без описания'}"
                    )
            
            if not incomes.exists() and not expenses.exists():
                lines.append("\n_Транзакции не найдены по указанным фильтрам_")
            
            return "\n".join(lines)
        except Exception as e:
            return f"## 💰 Транзакции\n\n_Ошибка: {e}_"
    
    def _build_goals_section(self) -> str:
        """Строит секцию с целями пользователя"""
        # Здесь можно добавить модель Goals в будущем
        # Пока заглушка
        return ""
    
    def _build_user_profile_section(self) -> str:
        """Строит секцию с профилем поведения пользователя"""
        try:
            # Анализируем паттерны поведения
            total_income = Income.objects.filter(user=self.user).aggregate(
                total=Sum('amount'),
                avg=Avg('amount'),
                count=Count('id')
            )
            
            total_expense = Expense.objects.filter(user=self.user).aggregate(
                total=Sum('amount'),
                avg=Avg('amount'),
                count=Count('id')
            )
            
            # Количество месяцев с данными
            first_transaction = Income.objects.filter(user=self.user).order_by('date').first()
            if not first_transaction:
                first_transaction = Expense.objects.filter(user=self.user).order_by('date').first()
            
            months_active = 0
            if first_transaction:
                delta = date.today() - first_transaction.date
                months_active = delta.days // 30
            
            lines = ["## 👤 Профиль пользователя"]
            lines.append(f"\n**Период активности:** {months_active} месяц(ев)")
            lines.append(f"**Всего транзакций:** {total_income['count'] + total_expense['count']}")
            
            if total_income['avg']:
                lines.append(f"**Средний доход:** {_format_currency(total_income['avg'])}")
            if total_expense['avg']:
                lines.append(f"**Средний расход:** {_format_currency(total_expense['avg'])}")
            
            # Определяем финансовый тип
            if total_income['total'] and total_expense['total']:
                ratio = total_expense['total'] / total_income['total']
                if ratio < 0.5:
                    financial_type = "Накопитель (тратите менее 50% доходов)"
                elif ratio < 0.8:
                    financial_type = "Оптимизатор (разумные траты)"
                elif ratio < 1.0:
                    financial_type = "Балансир (на грани)"
                else:
                    financial_type = "Расточитель (траты превышают доходы!) ⚠️"
                
                lines.append(f"**Финансовый тип:** {financial_type}")
            
            return "\n".join(lines)
        except Exception as e:
            return ""
    
    def _filter_months_by_period(
        self, 
        months: Dict[str, Any], 
        ordered_keys: List[str], 
        time_period: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Фильтрует месяцы по временному периоду"""
        if not time_period.get('start_date') or not months:
            return months
        
        start_key = _month_key(time_period['start_date'])
        end_key = _month_key(time_period.get('end_date', date.today()))
        
        filtered = {}
        for key in ordered_keys:
            if start_key <= key <= end_key:
                filtered[key] = months[key]
        
        return filtered
    
    def _build_custom_table(self, months: Dict[str, Any]) -> str:
        """Строит custom таблицу для отфильтрованных месяцев"""
        if not months:
            return "_Нет данных за указанный период_"
        
        header = "| Месяц | Доходы | Расходы | Баланс |\n|---|---|---|---|"
        lines = [header]
        
        for month_key in sorted(months.keys()):
            data = months[month_key]
            lines.append(
                f"| {month_key} | {_format_currency(data.get('income_total', 0))} | "
                f"{_format_currency(data.get('expense_total', 0))} | "
                f"{_format_currency(data.get('balance', 0))} |"
            )
        
        return "\n".join(lines)


def build_enriched_context(user, query_analysis: Dict[str, Any]) -> str:
    """
    Удобная функция для построения контекста.
    
    Args:
        user: Django User object
        query_analysis: Результат анализа запроса
        
    Returns:
        Markdown-форматированный контекст
    """
    builder = ContextBuilder(user)
    return builder.build(query_analysis)
