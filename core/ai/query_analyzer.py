"""
Анализатор запросов пользователя для определения типа финансового вопроса
и подготовки релевантного контекста.
"""

import re
from typing import Dict, List, Any, Tuple
from datetime import datetime, date, timedelta


class QueryType:
    """Типы финансовых запросов"""
    TRENDS = 'trends'           # Тренды и анализ
    ANOMALIES = 'anomalies'     # Аномалии и странные траты
    ADVICE = 'advice'           # Советы по оптимизации
    COMPARISON = 'comparison'   # Сравнение периодов
    FORECAST = 'forecast'       # Прогноз
    SPECIFIC = 'specific'       # Конкретная транзакция/категория
    GOALS = 'goals'             # Финансовые цели
    GENERAL = 'general'         # Общие вопросы


class QueryAnalyzer:
    """
    Анализатор запросов для определения намерений пользователя
    и построения релевантного контекста.
    """
    
    # Ключевые слова для каждого типа запроса
    KEYWORDS = {
        QueryType.TRENDS: [
            'тренд', 'динамик', 'изменени', 'рост', 'падени', 'увеличи', 'уменьши',
            'trend', 'dynamic', 'change', 'growth', 'decline',
            'как изменил', 'что происход', 'куда движ'
        ],
        QueryType.ANOMALIES: [
            'аномали', 'странн', 'необычн', 'подозрительн', 'неожиданн',
            'anomaly', 'unusual', 'suspicious', 'strange',
            'почему так мног', 'откуда такие', 'что случил'
        ],
        QueryType.ADVICE: [
            'совет', 'рекоменд', 'что делать', 'как улучш', 'как сэконом',
            'advice', 'recommend', 'improve', 'optimize', 'save',
            'помоги', 'подскажи', 'как можно'
        ],
        QueryType.COMPARISON: [
            'сравни', 'разниц', 'чем отличается', 'vs', 'против',
            'compare', 'difference', 'versus',
            'прошл месяц', 'в прошлом году', 'раньше'
        ],
        QueryType.FORECAST: [
            'прогноз', 'предскаж', 'будущ', 'ожидается', 'планиру',
            'forecast', 'predict', 'future', 'expect',
            'что будет', 'сколько буд', 'когда дости'
        ],
        QueryType.SPECIFIC: [
            'категори', 'расход', 'доход', 'транзакци', 'платеж',
            'category', 'expense', 'income', 'transaction',
            'сколько потра', 'сколько зараб'
        ],
        QueryType.GOALS: [
            'цель', 'накопи', 'план', 'хочу', 'мечта',
            'goal', 'save up', 'target', 'want',
            'сколько нужно', 'когда смогу'
        ],
    }
    
    # Временные маркеры
    TIME_MARKERS = {
        'сегодня': 0,
        'вчера': 1,
        'позавчера': 2,
        'неделя': 7,
        'месяц': 30,
        'квартал': 90,
        'год': 365,
        'today': 0,
        'yesterday': 1,
        'week': 7,
        'month': 30,
        'quarter': 90,
        'year': 365,
    }
    
    def __init__(self):
        self.query_text = ""
        self.detected_types = []
        self.detected_categories = []
        self.detected_time_period = None
        self.detected_amounts = []
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Анализирует запрос и возвращает структурированную информацию.
        
        Args:
            query: Текст запроса пользователя
            
        Returns:
            Dict с типом запроса, категориями, периодами и т.д.
        """
        self.query_text = query.lower()
        
        # Определяем тип запроса
        query_type = self._detect_query_type()
        
        # Извлекаем категории
        categories = self._extract_categories()
        
        # Извлекаем временной период
        time_period = self._extract_time_period()
        
        # Извлекаем суммы
        amounts = self._extract_amounts()
        
        # Определяем приоритет данных для контекста
        context_priority = self._get_context_priority(query_type)
        
        return {
            'query_type': query_type,
            'categories': categories,
            'time_period': time_period,
            'amounts': amounts,
            'context_priority': context_priority,
            'requires_deep_search': query_type in [QueryType.SPECIFIC, QueryType.ANOMALIES],
            'requires_forecast': query_type == QueryType.FORECAST,
            'requires_comparison': query_type == QueryType.COMPARISON,
        }
    
    def _detect_query_type(self) -> str:
        """Определяет тип запроса по ключевым словам"""
        scores = {val: 0 for key, val in QueryType.__dict__.items() if not key.startswith('_')}
        
        for query_type, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword in self.query_text:
                    scores[query_type] += 1
        
        # Возвращаем тип с максимальным score
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return QueryType.GENERAL
    
    def _extract_categories(self) -> List[str]:
        """Извлекает упомянутые категории из запроса"""
        common_categories = [
            'еда', 'продукты', 'питание', 'food',
            'транспорт', 'бензин', 'transport',
            'развлечения', 'entertainment',
            'здоровье', 'медицина', 'health',
            'одежда', 'clothes',
            'образование', 'education',
            'жилье', 'аренда', 'коммунал', 'housing', 'rent',
            'зарплата', 'salary',
            'маркетинг', 'реклама', 'marketing',
            'офис', 'office',
        ]
        
        found = []
        for cat in common_categories:
            if cat in self.query_text:
                found.append(cat)
        
        return found
    
    def _extract_time_period(self) -> Dict[str, Any]:
        """Извлекает временной период из запроса"""
        result = {
            'type': None,  # 'last_n_days', 'specific_month', 'date_range'
            'days_ago': None,
            'start_date': None,
            'end_date': None,
        }
        
        # Проверяем маркеры времени
        for marker, days in self.TIME_MARKERS.items():
            if marker in self.query_text:
                result['type'] = 'last_n_days'
                result['days_ago'] = days
                result['start_date'] = date.today() - timedelta(days=days)
                result['end_date'] = date.today()
                break
        
        # Проверяем конкретные месяцы
        months_ru = {
            'январ': 1, 'феврал': 2, 'март': 3, 'апрел': 4,
            'ма': 5, 'июн': 6, 'июл': 7, 'август': 8,
            'сентябр': 9, 'октябр': 10, 'ноябр': 11, 'декабр': 12,
        }
        
        for month_name, month_num in months_ru.items():
            if month_name in self.query_text:
                result['type'] = 'specific_month'
                # Определяем год (текущий или прошлый)
                year = datetime.now().year
                if 'прошл' in self.query_text:
                    year -= 1
                result['start_date'] = date(year, month_num, 1)
                # Последний день месяца
                if month_num == 12:
                    result['end_date'] = date(year, 12, 31)
                else:
                    result['end_date'] = date(year, month_num + 1, 1) - timedelta(days=1)
                break
        
        # Если ничего не найдено, берем последние 3 месяца
        if result['type'] is None:
            result['type'] = 'last_n_days'
            result['days_ago'] = 90
            result['start_date'] = date.today() - timedelta(days=90)
            result['end_date'] = date.today()
        
        return result
    
    def _extract_amounts(self) -> List[float]:
        """Извлекает числовые значения (суммы) из запроса"""
        # Ищем числа в тексте
        amounts = []
        # Паттерн: число может быть с пробелами (1 000) или без (1000)
        pattern = r'\b\d{1,3}(?:[\s,]\d{3})*(?:\.\d+)?\b'
        matches = re.findall(pattern, self.query_text)
        
        for match in matches:
            # Убираем пробелы и запятые
            clean = match.replace(' ', '').replace(',', '')
            try:
                amounts.append(float(clean))
            except ValueError:
                continue
        
        return amounts
    
    def _get_context_priority(self, query_type: str) -> List[str]:
        """
        Определяет приоритет данных для контекста в зависимости от типа запроса.
        
        Returns:
            List в порядке приоритета: ['tables', 'trends', 'anomalies', 'goals', 'transactions']
        """
        priorities = {
            QueryType.TRENDS: ['trends', 'tables', 'anomalies'],
            QueryType.ANOMALIES: ['anomalies', 'transactions', 'tables'],
            QueryType.ADVICE: ['trends', 'anomalies', 'goals', 'tables'],
            QueryType.COMPARISON: ['tables', 'trends'],
            QueryType.FORECAST: ['trends', 'tables', 'goals'],
            QueryType.SPECIFIC: ['transactions', 'tables'],
            QueryType.GOALS: ['goals', 'trends', 'tables'],
            QueryType.GENERAL: ['tables', 'trends', 'anomalies'],
        }
        
        return priorities.get(query_type, ['tables', 'trends'])


def analyze_query(query: str) -> Dict[str, Any]:
    """
    Удобная функция для анализа запроса.
    
    Args:
        query: Текст запроса пользователя
        
    Returns:
        Результат анализа
    """
    analyzer = QueryAnalyzer()
    return analyzer.analyze(query)
