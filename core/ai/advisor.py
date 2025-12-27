"""
Улучшенный финансовый советчик с умным подбором контекста
и персонализированными советами.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from core.ai.query_analyzer import analyze_query
from core.ai.context_builder import build_enriched_context
from core.llm import chat_with_context
from core.models import ChatSession, ChatMessage
from django.conf import settings


# Улучшенный системный промпт для финансового советчика
ADVANCED_FINANCIAL_PROMPT = """
**CRITICAL: You MUST respond ONLY in English. Never use Russian or any other language in your responses.**

You are a **Personal Financial Analyst and Advisor** of the highest level.

# YOUR ROLE
You are NOT just an AI chatbot. You are a virtual CFO for small businesses and personal finances.

# CRITICAL PRINCIPLES

## 1. DEPTH OF ANALYSIS ⚡
- Analyze NOT just numbers, but **behavior patterns**
- Look for **hidden correlations** between categories
- Identify **seasonality** and **cyclicality** of spending
- Detect **psychological triggers** for expenses

## 2. PERSONALIZATION 🎯
- Consider the user's **financial type** (saver/optimizer/balancer/spender)
- Adapt advice to the **current stage of the financial journey**
- Remember context from **previous dialogues** in the session
- Use **behavior profile** for forecasts

## 3. ACTIONABLE ADVICE ✅
Every piece of advice MUST contain:
- 🎯 **WHAT** to do (specific action)
- 📊 **WHY** it is important (data and analysis)
- 📈 **RESULT** (expected effect with numbers)
- ⏱️ **WHEN** to execute (urgency)
- 🔧 **HOW** to implement (step-by-step plan)

## 4. RESPONSE FORMAT 📋

### Response Structure:
```
## 🎯 QUICK CONCLUSION (1-2 sentences)
[Most important insight]

## 📊 KEY FINDINGS
- [Insight 1 with numbers]
- [Insight 2 with trend]
- [Insight 3 with anomaly]

## 🚨 CRITICAL MOMENTS (if any)
- [Problem] → [Consequences] → [Urgency]

## 💡 PRIORITY RECOMMENDATIONS

### 🔥 NOW (this week):
1. [Action + expected result + how to do it]
2. ...

### 📆 THIS MONTH:
1. [Medium-term task]
2. ...

### 🔮 LONG-TERM (3-6 months):
1. [Strategic recommendation]
2. ...

## 📈 FORECAST (if enough data)
- With current trends in a month: [numbers]
- To achieve goal [X] you need: [plan]

## 🎓 FINANCIAL LITERACY
[1 tip/lifehack/principle the user might not know]
```

## 5. PROBLEM DETECTION 🚩

Automatically ALERT if:
- ❗ Expenses grew >30% in a month
- ❗ Income dropped >20%
- ❗ Negative balance for 2+ months in a row
- ❗ One category >40% of all expenses
- ❗ No savings with income > expenses

## 6. FORBIDDEN ⛔

- ❌ "Fluff" and general phrases without numbers
- ❌ Repeating the obvious from the table
- ❌ Giving advice "just in case"
- ❌ Ignoring context from the profile
- ❌ Advising things already being done

## 7. USE ALL CONTEXT 🧠

Available to you:
- 📊 Full transaction history
- 📈 Trends for all months
- 🔍 Detected anomalies
- 👤 User behavior profile
- 💬 Dialogue history in session

**IMPORTANT:** Use this data to build INSIGHTS, not just a recap!

## 8. TONE 🎭

- Friendly but professional
- Motivating but realistic
- Honest even with bad news
- Supportive during setbacks

## 9. OFF-TOPIC 🚫

You are a specialized financial assistant.
If the user request:
1. Does not concern finances, money, purchases, economics, or goals.
2. And is not a greeting or "small talk".
3. And does not concern the interface or functions of this application.

THEN:
- IGNORE ALL FORMATTING RULES (section 4).
- Reply ONLY: "This message has nothing to do with our financial project."
- DO NOT generate any headers or financial advice.
---

# USER CONTEXT

{enriched_context}

---

**INSTRUCTION FOR RESPONSE:**
Based on the context above and the user's question, provide the most useful, insightful, and actionable answer.
Remember: your goal is to genuinely improve the user's financial well-being, not just answer the question.
"""


class EnhancedFinancialAdvisor:
    """
    Улучшенный финансовый советчик с умным анализом запросов
    и персонализированными советами.
    """
    
    def __init__(self, user, session: Optional[ChatSession] = None):
        self.user = user
        self.session = session
    
    def get_advice(
        self, 
        user_query: str,
        use_local: bool = False,
        anonymize: bool = True
    ) -> Dict[str, Any]:
        """
        Получает персонализированный совет на основе запроса.
        
        Args:
            user_query: Вопрос пользователя
            use_local: Использовать локальную модель (Ollama)
            anonymize: Анонимизировать данные перед отправкой в облако
            
        Returns:
            Dict с ответом и метаданными
        """
        # 1. Анализируем запрос
        query_analysis = analyze_query(user_query)
        
        # 2. Строим обогащенный контекст
        enriched_context = build_enriched_context(self.user, query_analysis)
        
        # 3. Формируем системный промпт
        system_prompt = ADVANCED_FINANCIAL_PROMPT.format(
            enriched_context=enriched_context
        )
        
        # 4. Получаем историю диалога если есть сессия
        messages = []
        if self.session:
            # Берем последние 10 сообщений для контекста
            history = ChatMessage.objects.filter(
                session=self.session
            ).order_by('-created_at')[:10]
            
            for msg in reversed(list(history)):
                messages.append({
                    'role': msg.role,
                    'content': msg.content
                })
        
        # Добавляем текущий запрос
        messages.append({
            'role': 'user',
            'content': user_query
        })
        
        # 5. Получаем ответ от LLM
        response = chat_with_context(
            messages=messages,
            user_data="",  # Уже включено в system_prompt через format
            session=self.session,
            check_duplicates=True,
            anonymize=anonymize,
            use_local=use_local,
            user=self.user,
            system_instruction=system_prompt  # <-- Передаем наш кастомный промпт
        )
        
        # 6. Обновляем timestamp сессии если есть
        if self.session:
            self.session.save()
        
        return {
            'response': response,
            'query_type': query_analysis['query_type'],
            'context_used': {
                'categories': query_analysis.get('categories', []),
                'time_period': query_analysis.get('time_period', {}),
                'priority': query_analysis.get('context_priority', []),
            },
            'metadata': {
                'requires_forecast': query_analysis.get('requires_forecast', False),
                'requires_comparison': query_analysis.get('requires_comparison', False),
                'context_size': len(enriched_context),
            }
        }
    
    def get_quick_insights(self) -> Dict[str, Any]:
        """
        Получает быстрые инсайты без конкретного вопроса.
        Полезно для дашборда "Что нового?".
        
        Returns:
            Dict с инсайтами и рекомендациями
        """
        # Используем специальный запрос для общего анализа
        return self.get_advice(
            "Give a brief analysis of my financial situation and give 2-3 most important tips right now.",
            use_local=False,
            anonymize=True
        )


def get_financial_advice(
    user,
    query: str,
    session: Optional[ChatSession] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Удобная функция для получения финансового совета.
    
    Args:
        user: Django User object
        query: Вопрос пользователя
        session: ChatSession (опционально)
        **kwargs: Дополнительные параметры (use_local, anonymize)
        
    Returns:
        Dict с ответом и метаданными
    """
    advisor = EnhancedFinancialAdvisor(user, session)
    return advisor.get_advice(query, **kwargs)
