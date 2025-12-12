#!/usr/bin/env python
"""
Скрипт для тестирования новой AI системы.

Запуск:
    python test_ai_system.py

Что тестирует:
    - Query Analyzer
    - Context Builder
    - Enhanced Advisor
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sb_finance.settings')
django.setup()

from datetime import date, timedelta
from django.contrib.auth.models import User
from core.ai.query_analyzer import analyze_query
from core.ai.context_builder import build_enriched_context
from core.ai.advisor import get_financial_advice
from core.models import Income, Expense, ChatSession


def test_query_analyzer():
    """Тестирует Query Analyzer"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Query Analyzer")
    print("="*60)
    
    test_queries = [
        "Как изменились мои расходы за последние 3 месяца?",
        "Почему так много трат на маркетинг в ноябре?",
        "Дай совет как сэкономить на офисе",
        "Сравни октябрь и ноябрь по расходам",
        "Что будет с моими финансами через полгода?",
        "Сколько я потратил на еду?",
    ]
    
    for query in test_queries:
        print(f"\n📝 Запрос: {query}")
        result = analyze_query(query)
        print(f"   Тип: {result['query_type']}")
        print(f"   Категории: {result['categories']}")
        print(f"   Период: {result['time_period']['type']}")
        print(f"   Приоритет данных: {result['context_priority']}")


def test_context_builder(user):
    """Тестирует Context Builder"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Context Builder")
    print("="*60)
    
    query = "Как изменились расходы на маркетинг?"
    print(f"\n📝 Запрос: {query}")
    
    analysis = analyze_query(query)
    context = build_enriched_context(user, analysis)
    
    print(f"\n📊 Построенный контекст ({len(context)} символов):")
    print("-" * 60)
    # Показываем первые 500 символов
    print(context[:500] + "..." if len(context) > 500 else context)


def test_enhanced_advisor(user):
    """Тестирует Enhanced Advisor"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Enhanced Financial Advisor")
    print("="*60)
    
    # Создаем тестовую сессию
    session = ChatSession.objects.create(
        user=user,
        title="Тестовая сессия"
    )
    
    query = "Как мне улучшить финансовую ситуацию?"
    print(f"\n📝 Запрос: {query}")
    print("⏳ Отправка запроса в LLM...")
    
    try:
        result = get_financial_advice(
            user=user,
            query=query,
            session=session,
            use_local=False,
            anonymize=True
        )
        
        print(f"\n✅ Получен ответ!")
        print(f"   Тип запроса: {result['query_type']}")
        print(f"   Размер контекста: {result['metadata']['context_size']} символов")
        print(f"\n💬 Ответ AI:")
        print("-" * 60)
        print(result['response'][:800] + "..." if len(result['response']) > 800 else result['response'])
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nПроверьте:")
        print("  - Установлен ли LLM_API_KEY в .env")
        print("  - Есть ли интернет подключение")
        print("  - Верный ли API endpoint")
    
    finally:
        session.delete()


def create_test_data(user):
    """Создает тестовые данные если их нет"""
    # Проверяем есть ли данные
    if Income.objects.filter(user=user).exists():
        print("\n✅ У пользователя уже есть финансовые данные")
        return
    
    print("\n📦 Создаем тестовые данные...")
    
    # Создаем доходы за последние 3 месяца
    for month_offset in range(3):
        month_date = date.today() - timedelta(days=30 * month_offset)
        
        # Доход
        Income.objects.create(
            user=user,
            amount=50000 + (month_offset * 5000),
            date=month_date,
            category='salary',
            description=f'Зарплата за {month_date.strftime("%B")}'
        )
        
        # Расходы
        expenses = [
            ('marketing', 12000 + (month_offset * 2000), 'Реклама в соцсетях'),
            ('office', 8000, 'Аренда офиса'),
            ('transport', 5000, 'Бензин'),
            ('food', 15000, 'Продукты и обеды'),
        ]
        
        for cat, amount, desc in expenses:
            Expense.objects.create(
                user=user,
                amount=amount,
                date=month_date + timedelta(days=5),
                category=cat,
                description=desc
            )
    
    print("✅ Тестовые данные созданы")


def main():
    """Главная функция"""
    print("\n" + "🤖 " + "="*58)
    print("    ТЕСТИРОВАНИЕ НОВОЙ AI СИСТЕМЫ")
    print("="*60)
    
    # Получаем или создаем тестового пользователя
    try:
        user = User.objects.filter(is_active=True).first()
        if not user:
            print("\n⚠️  Не найден активный пользователь!")
            print("Создайте пользователя через: python manage.py createsuperuser")
            return
        
        print(f"\n👤 Пользователь: {user.username}")
        
        # Создаем тестовые данные если нужно
        create_test_data(user)
        
        # Запускаем тесты
        test_query_analyzer()
        test_context_builder(user)
        
        # Тест с LLM (опционально)
        print("\n" + "="*60)
        response = input("\nЗапустить тест с реальным LLM? (y/n): ")
        if response.lower() == 'y':
            test_enhanced_advisor(user)
        else:
            print("\n⏭️  Пропускаем тест с LLM")
        
        print("\n" + "="*60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
