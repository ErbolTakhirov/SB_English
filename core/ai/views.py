"""
Новая улучшенная версия AI chat API с использованием
умного анализа запросов и обогащенного контекста.

Добавьте этот код в urls.py:
    path('api/ai/chat/v2/', views.ai_chat_api_v2, name='ai_chat_v2'),
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
import json
import uuid

from core.models import ChatSession, ChatMessage
from core.ai.advisor import get_financial_advice
from core.utils.analytics import parse_actionable_items
from core.llm import _compute_content_hash


@csrf_exempt
@login_required
def ai_chat_api_v2(request):
    """
    Улучшенная версия AI chat API с умным анализом запросов
    и персонализированным контекстом.
    
    Новые возможности:
    - Автоматический анализ типа запроса (тренды/аномалии/советы/etc.)
    - Умный подбор контекста на основе запроса
    - Персонализированный профиль пользователя
    - Группировка советов по приоритетам
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    
    # Парсим запрос
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
    except:
        data = request.POST.dict()
    
    msg = data.get('message', '').strip()
    session_id = data.get('session_id')
    
    if not msg:
        return JsonResponse({'ok': False, 'error': 'Пустое сообщение'}, status=400)
    
    if len(msg) > 5000:
        return JsonResponse({
            'ok': False, 
            'error': 'Сообщение слишком длинное (максимум 5000 символов)'
        }, status=400)
    
    # Настройки приватности
    use_local = data.get('use_local', False)
    anonymize = data.get('anonymize', True)
    
    try:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.local_mode_only:
            use_local = True
        use_local = request.session.get('use_local_llm', use_local)
        anonymize = request.session.get('anonymize_enabled', anonymize)
    except:
        pass
    
    # Получаем или создаем сессию
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                session_id=session_id, 
                user=request.user,
                title=msg[:50] + ('...' if len(msg) > 50 else '')
            )
    else:
        session_id = str(uuid.uuid4())
        session = ChatSession.objects.create(
            session_id=session_id,
            user=request.user,
            title=msg[:50] + ('...' if len(msg) > 50 else '')
    )
    
    # Автоматически генерируем название если пустое
    if not session.title:
        session.title = msg[:50] + ('...' if len(msg) > 50 else '')
        session.save()
    
    try:
        # 1. Сохраняем сообщение пользователя
        ChatMessage.objects.create(
            session=session,
            role='user',
            content=msg,
            content_hash=_compute_content_hash(msg)
        )

        # 2. ИСПОЛЬЗУЕМ НОВЫЙ УЛУЧШЕННЫЙ СОВЕТНИК
        result = get_financial_advice(
            user=request.user,
            query=msg,
            session=session,
            use_local=use_local,
            anonymize=anonymize
        )
        
        reply = result['response']
        query_type = result.get('query_type', 'general')
        context_used = result.get('context_used', {})
        metadata = result.get('metadata', {})
        
        # 3. Сохраняем сообщение ассистента
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=reply,
            content_hash=_compute_content_hash(reply)
        )
        
        # Извлекаем actionable советы
        actionable_items = parse_actionable_items(reply)
        
        # Группируем по секциям и приоритетам
        advice_by_section = {
            'now': [],
            'this_month': [],
            'future': [],
            'urgent': [],
            'quick_win': [],
            'long_term': [],
            'general': [],
        }
        
        for item in actionable_items:
            section = item.get('section', 'general')
            priority = item.get('priority', 'normal')
            
            # Группировка по секции
            if section in advice_by_section:
                advice_by_section[section].append(item)
            
            # Группировка по приоритету
            if priority in advice_by_section:
                advice_by_section[priority].append(item)
            
            # Fallback в general
            if section not in advice_by_section and priority not in advice_by_section:
                advice_by_section['general'].append(item)
        
        # Обновляем action_log
        try:
            action_log = dict(session.action_log or {})
            action_log['advices_given'] = action_log.get('advices_given', 0) + len(actionable_items)
            action_log['last_advice_at'] = timezone.now().isoformat()
            action_log['total_messages'] = action_log.get('total_messages', 0) + 1
            action_log['query_types'] = action_log.get('query_types', [])
            action_log['query_types'].append({
                'type': query_type,
                'timestamp': timezone.now().isoformat()
            })
            
            # Сохраняем все советы с новыми полями
            if 'all_advices' not in action_log:
                action_log['all_advices'] = []
            
            for item in actionable_items:
                advice_id = str(uuid.uuid4())[:8]
                action_log['all_advices'].append({
                    'id': advice_id,
                    'text': item.get('text', ''),
                    'type': item.get('type', 'unknown'),
                    'section': item.get('section', 'general'),
                    'priority': item.get('priority', 'normal'),
                    'query_type': query_type,  # Новое поле
                    'created_at': timezone.now().isoformat(),
                    'completed': False,
                })
            
            session.action_log = action_log
            session.save()
        except Exception as e:
            print(f"Ошибка обновления action_log: {e}")
        
        # Получаем активные советы
        active_advices = []
        try:
            all_advices = action_log.get('all_advices', [])
            active_advices = [a for a in all_advices if not a.get('completed', False)]
        except:
            pass
        
        return JsonResponse({
            'ok': True,
            'reply': reply,
            'session_id': session_id,
            'used_local': use_local,
            'anonymize': anonymize,
            
            # Метаданные анализа
            'query_type': query_type,
            'context_used': context_used,
            'metadata': metadata,
            
            # Actionable советы
            'actionable_items': actionable_items,
            'actionable_by_section': advice_by_section,
            'actionable_count': len(actionable_items),
            
            # Активные советы из сессии
            'active_advices': active_advices,
            'active_advices_count': len(active_advices),
            
            # Статистика сессии
            'session_stats': {
                'total_messages': action_log.get('total_messages', 0),
                'advices_given': action_log.get('advices_given', 0),
                'advices_completed': action_log.get('advices_completed', 0),
            },
            
            # Версия API
            'api_version': 'v2',
            'enhanced': True,
        })
        
    except Exception as ex:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Ошибка в ai_chat_api_v2: {ex}")
        print(error_trace)
        
        response_data = {
            'ok': False,
            'error': f'Ошибка обработки запроса: {str(ex)}'
        }
        
        if settings.DEBUG:
            response_data['traceback'] = error_trace
        
        return JsonResponse(response_data, status=500)
