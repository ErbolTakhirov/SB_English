import json
import hashlib
import re
from typing import List, Dict, Any, Optional, Set

import requests
from django.conf import settings
from django.db.models import Q

from core.models import ChatMessage, ChatSession
from core.utils.anonymizer import anonymize_text, anonymize_csv_data
from core.utils.analytics import (
    get_user_financial_memory,
    build_system_prompt,
    parse_actionable_items,
    detect_anomalies_automatically,
)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# ============================================================================
# КОНФИГУРАЦИЯ API LLM
# ============================================================================
# Вставьте ваш API ключ в settings.py или .env файл:
# LLM_API_KEY=your_api_key_here
# LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
# LLM_MODEL=openai/gpt-4o-mini
# ============================================================================

def _headers() -> Dict[str, str]:
    """
    Формирует заголовки для запроса к LLM API.
    OpenRouter требует дополнительные заголовки.
    """
    headers = {
        'Content-Type': 'application/json',
    }
    
    # ВАЖНО: Вставьте ваш API ключ в settings.LLM_API_KEY
    if settings.LLM_API_KEY:
        headers['Authorization'] = f"Bearer {settings.LLM_API_KEY}"
    
    # OpenRouter требует эти заголовки (опционально, но рекомендуются)
    # Referer: URL вашего сайта (для отслеживания использования API)
    # X-Title: Название вашего приложения (для отображения в статистике OpenRouter)
    referer = getattr(settings, 'LLM_HTTP_REFERER', 'http://localhost:8000')
    app_title = getattr(settings, 'LLM_APP_TITLE', 'SB Finance AI')
    
    # Добавляем заголовки только если они настроены
    if referer:
        headers['Referer'] = referer
    if app_title:
        headers['X-Title'] = app_title
    
    return headers


def _compute_content_hash(content: str) -> str:
    """Вычисляет SHA256 хеш содержимого для проверки на повторения"""
    # Нормализуем: удаляем лишние пробелы, приводим к нижнему регистру для сравнения
    normalized = re.sub(r'\s+', ' ', content.strip().lower())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _extract_advice_snippets(content: str) -> List[str]:
    """Извлекает отдельные советы из текста для проверки на повторения"""
    snippets = []
    # Ищем списки, пункты, параграфы
    lines = content.split('\n')
    current_snippet = []
    for line in lines:
        line = line.strip()
        if not line:
            if current_snippet:
                snippets.append(' '.join(current_snippet))
                current_snippet = []
            continue
        # Проверяем, начинается ли строка с маркера списка
        if re.match(r'^[-*•\d+\.]', line):
            if current_snippet:
                snippets.append(' '.join(current_snippet))
            current_snippet = [line]
        else:
            current_snippet.append(line)
    if current_snippet:
        snippets.append(' '.join(current_snippet))
    return snippets


def _check_for_duplicates(new_content: str, session: ChatSession, similarity_threshold: float = 0.8) -> bool:
    """
    Проверяет, есть ли похожие советы в истории сессии.
    Возвращает True, если найдены дубликаты.
    similarity_threshold: порог схожести (0-1), по умолчанию 0.8
    """
    new_hash = _compute_content_hash(new_content)
    new_snippets = _extract_advice_snippets(new_content)
    
    # Получаем все предыдущие ответы ассистента в этой сессии
    previous_messages = ChatMessage.objects.filter(
        session=session,
        role='assistant'
    ).exclude(content_hash=new_hash)
    
    for prev_msg in previous_messages:
        prev_hash = prev_msg.content_hash
        # Простая проверка по хешу
        if new_hash == prev_hash:
            return True
        
        # Проверка по извлеченным фрагментам
        prev_snippets = _extract_advice_snippets(prev_msg.content)
        for new_snip in new_snippets:
            new_snip_hash = _compute_content_hash(new_snip)
            for prev_snip in prev_snippets:
                prev_snip_hash = _compute_content_hash(prev_snip)
                # Если хеши совпадают или очень похожи по длине и содержанию
                if new_snip_hash == prev_snip_hash:
                    return True
                # Дополнительная проверка: если один фрагмент содержит другой
                if len(new_snip) > 20 and len(prev_snip) > 20:
                    new_lower = new_snip.lower()
                    prev_lower = prev_snip.lower()
                    if new_lower in prev_lower or prev_lower in new_lower:
                        return True
    
    return False


def get_ai_advice_from_data(data_blob: str, extra_instruction: str = "", anonymize: bool = True, user=None) -> str:
    """
    Sends a single-shot prompt with user data embedded into the system message.
    data_blob: CSV or compact JSON string with user's transactions/metrics.
    extra_instruction: optional user question or context.
    anonymize: если True, анонимизирует данные перед отправкой в облако.
    user: User объект для получения финансовой памяти (таблиц, summary)
    """
    # Если передан user, используем финансовую память с таблицами
    if user:
        try:
            memory = get_user_financial_memory(user, force_refresh=False)
            # Проверяем наличие ключевых полей в памяти
            if memory and isinstance(memory, dict) and memory.get('table_markdown'):
                # Используем новый формат с таблицами
                system_content = build_system_prompt(memory, extra_context=data_blob or "")
            else:
                # Fallback на старый формат, если память пустая или неверный формат
                if anonymize:
                    anonymized_data = anonymize_csv_data(data_blob)
                    system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=anonymized_data)
                else:
                    system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=data_blob)
        except Exception as e:
            # Fallback на старый формат при ошибке
            import traceback
            print(f"Ошибка при получении финансовой памяти для AI: {e}")
            print(traceback.format_exc())
            if anonymize:
                anonymized_data = anonymize_csv_data(data_blob)
                system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=anonymized_data)
            else:
                system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=data_blob)
    else:
        # Старый формат без памяти
        if anonymize:
            anonymized_data = anonymize_csv_data(data_blob)
            system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=anonymized_data)
        else:
            system_content = settings.LLM_PROMPT_TEMPLATE.format(user_data=data_blob)
    
    messages = [
        {"role": "system", "content": system_content},
    ]
    if extra_instruction:
        messages.append({"role": "user", "content": extra_instruction})

    # Получаем модель из настроек или параметров запроса
    model = getattr(settings, 'LLM_MODEL', 'deepseek-chat-v3.1:free')
    
    payload = {
        "model": model,  # Явно указываем модель в параметрах запроса
        "messages": messages,
        "max_tokens": getattr(settings, 'LLM_MAX_TOKENS', 4000),  # Ограничиваем токены для экономии
    }
    try:
        resp = requests.post(settings.LLM_API_URL, headers=_headers(), json=payload, timeout=60)
        
        if resp.status_code != 200:
            error_detail = f"HTTP {resp.status_code}"
            try:
                error_data = resp.json()
                if 'error' in error_data:
                    error_msg = error_data['error'].get('message', str(error_data['error']))
                    error_detail = error_msg
                    # Проверяем на лимиты free tier
                    if 'limit' in error_msg.lower() or 'quota' in error_msg.lower() or 'free' in error_msg.lower():
                        error_detail = f"⚠️ Достигнут лимит бесплатного тарифа. {error_msg}\n\nПопробуйте позже или используйте платную модель."
            except:
                error_detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            return f"[AI ошибка] {error_detail}"
        
        data = resp.json()
        if 'choices' not in data or not data['choices']:
            return "[AI ошибка] Неожиданный формат ответа от API."
        return data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as ex:
        return f"[AI ошибка] Ошибка сети: {ex}"
    except Exception as ex:
        return f"[AI ошибка] Не удалось получить ответ модели: {ex}"


def chat_with_context(
    messages: List[Dict[str, str]], 
    user_data: str = "",
    session: Optional[ChatSession] = None,
    check_duplicates: bool = True,
    anonymize: bool = True,
    use_local: bool = False,
    user=None,
    system_instruction: Optional[str] = None
) -> str:
    """
    Chat-style call с поддержкой истории и проверкой на повторения.
    
    Args:
        messages: list of {role: 'user'|'assistant'|'system', content: str}
        user_data: CSV/JSON compact data to ground the answers (дополнительный контекст)
        session: ChatSession для сохранения истории и проверки на повторения
        check_duplicates: если True, проверяет на повторения советов
        anonymize: если True, анонимизирует данные перед отправкой в облако
        use_local: если True, использует локальную модель (Ollama)
        user: User объект для получения финансовой памяти
        system_instruction: Кастомный системный промпт (переопределяет стандартный)
    
    Returns:
        Ответ от LLM
    """
    # Локальный режим (Ollama)
    if use_local:
        return _call_local_llm(messages, user_data, user=user)
    
    # ------------------------------------------------------------------
    # Определяем, нужно ли использовать Google Gemini напрямую
    # ------------------------------------------------------------------
    model_name = getattr(settings, 'LLM_MODEL', 'deepseek-chat-v3.1:free').lower()
    has_google_key = bool(getattr(settings, 'GOOGLE_API_KEY', ''))
    has_llm_key = bool(getattr(settings, 'LLM_API_KEY', ''))
    
    # Инициализируем переменную memory
    memory = None

    # Используем Gemini напрямую если:
    # 1. Выбрана модель Gemini И есть Google API ключ (даже если есть OpenRouter ключ - прямой доступ надежнее)
    # 2. НЕТ OpenRouter ключа, но есть Google API ключ (fallback)
    is_gemini_model = 'gemini' in model_name
    use_google_direct = (is_gemini_model and has_google_key) or (has_google_key and not has_llm_key)
    
    if use_google_direct:
        # Для Gemini нам нужен sys_prompt отдельно
        if system_instruction:
            sys_prompt = system_instruction
        else:
            # Получаем финансовую память
            memory = None
            if user:
                try:
                    memory = get_user_financial_memory(user, force_refresh=False)
                except Exception:
                    pass
            
            if memory:
                 sys_prompt = build_system_prompt(memory, extra_context=user_data or "")
            else:
                 if anonymize and user_data:
                     anonymized_data = anonymize_csv_data(user_data)
                 else:
                     anonymized_data = user_data
                 sys_prompt = settings.LLM_PROMPT_TEMPLATE.format(user_data=anonymized_data or "Нет данных")
        
        if check_duplicates and session:
            sys_prompt += "\n\nВАЖНО: Не повторяй ранее данные советы в этой сессии. Всегда давай новые, уникальные рекомендации."
            
        return _call_google_gemini(messages, sys_prompt)
    
    # Если передан кастомный системный промпт, используем его
    if system_instruction:
        sys_prompt = system_instruction
    else:
        # Получаем финансовую память пользователя (таблицы, summary, alerts)
        memory = None
        if user:
            try:
                memory = get_user_financial_memory(user, force_refresh=False)
            except Exception:
                pass
        
        # Формируем системный промпт с таблицами и summary из памяти
        if memory:
            # Используем новый формат промпта с таблицами
            sys_prompt = build_system_prompt(memory, extra_context=user_data or "")
        else:
            # Fallback на старый формат, если памяти нет
            if anonymize and user_data:
                anonymized_data = anonymize_csv_data(user_data)
            else:
                anonymized_data = user_data
            sys_prompt = settings.LLM_PROMPT_TEMPLATE.format(user_data=anonymized_data or "Нет данных")
    
    # Добавляем инструкцию о недопустимости повторений
    if check_duplicates and session:
        sys_prompt += "\n\nВАЖНО: Не повторяй ранее данные советы в этой сессии. Всегда давай новые, уникальные рекомендации."
    
    # Анонимизируем сообщения пользователя (если используется облако и память не анонимизирована)
    if anonymize and not memory:
        anonymized_messages = []
        for msg in messages:
            if msg['role'] == 'user':
                anonymized_messages.append({
                    'role': msg['role'],
                    'content': anonymize_text(msg['content'])
                })
            else:
                anonymized_messages.append(msg)
        messages = anonymized_messages
    elif anonymize and memory:
        # Анонимизируем только пользовательские сообщения, но не таблицы
        anonymized_messages = []
        for msg in messages:
            if msg['role'] == 'user':
                anonymized_messages.append({
                    'role': msg['role'],
                    'content': anonymize_text(msg['content'])
                })
            else:
                anonymized_messages.append(msg)
        messages = anonymized_messages
    
    # Ограничиваем длину системного промпта (слишком длинные промпты могут вызывать ошибки)
    max_system_length = 8000  # Увеличиваем лимит для таблиц
    if len(sys_prompt) > max_system_length:
        # Обрезаем только дополнительный контекст, сохраняя таблицы
        if "### Дополнительный контекст" in sys_prompt:
            parts = sys_prompt.split("### Дополнительный контекст")
            sys_prompt = parts[0] + "\n\n### Дополнительный контекст\n[Данные обрезаны для оптимизации]"
        else:
            sys_prompt = sys_prompt[:max_system_length] + "\n\n[Данные обрезаны для оптимизации]"
    
    full_messages = [{"role": "system", "content": sys_prompt}] + messages
    
    # Получаем модель из настроек или параметров запроса
    model = getattr(settings, 'LLM_MODEL', 'deepseek-chat-v3.1:free')
    
    models_to_try = [model]
    
    # Добавляем fallback модели, если используемая модель бесплатная или экспериментальная
    if ':free' in model or 'exp' in model:
        fallbacks = [
            'google/gemini-2.0-flash-exp:free',
            'deepseek/deepseek-r1:free',
            'meta-llama/llama-3-8b-instruct:free',
            'deepseek/deepseek-chat',  # Cheap paid as last resort
        ]
        for fb in fallbacks:
            if fb != model and fb not in models_to_try:
                models_to_try.append(fb)
    
    last_error = ""
    
    for current_model in models_to_try:
        payload = {
            "model": current_model,
            "messages": full_messages,
            "max_tokens": getattr(settings, 'LLM_MAX_TOKENS', 4000),
        }
        
        try:
            # print(f"Trying model: {current_model}")
            resp = requests.post(settings.LLM_API_URL, headers=_headers(), json=payload, timeout=60)
            
            if resp.status_code == 200:
                data = resp.json()
                if 'choices' in data and data['choices']:
                    reply = data['choices'][0]['message']['content']
                    
                    # Проверяем на повторения, если включена проверка
                    if check_duplicates and session:
                        if _check_for_duplicates(reply, session):
                            sys_prompt += "\n\nОбнаружены повторения в предыдущих ответах. Пожалуйста, дай совершенно новый, уникальный совет, который еще не был дан в этой сессии."
                            full_messages = [{"role": "system", "content": sys_prompt}] + messages
                            payload['messages'] = full_messages
                            # Повторный запрос к той же модели
                            resp_retry = requests.post(settings.LLM_API_URL, headers=_headers(), json=payload, timeout=60)
                            if resp_retry.status_code == 200:
                                data_retry = resp_retry.json()
                                if 'choices' in data_retry and data_retry['choices']:
                                    return data_retry['choices'][0]['message']['content']
                    
                    return reply
            
            # Если ошибка, сохраняем и пробуем следующую
            try:
                err_data = resp.json()
                err_msg = err_data.get('error', {}).get('message', str(err_data))
                last_error = f"{current_model}: {err_msg}"
            except:
                last_error = f"{current_model}: HTTP {resp.status_code}"
                
        except Exception as e:
            last_error = f"{current_model}: {str(e)}"
            continue
            
    # Если ни одна модель не сработала
    return f"[AI Error] Все модели недоступны. Последняя ошибка: {last_error}"



def _call_local_llm(messages: List[Dict[str, str]], user_data: str = "", user=None) -> str:
    """
    Вызывает локальную LLM через Ollama API.
    ВАЖНО: Данные НЕ отправляются в облако, всё обрабатывается локально.
    
    Args:
        messages: История сообщений
        user_data: Данные пользователя
        user: User объект для получения финансовой памяти (опционально)
    
    Returns:
        Ответ от локальной LLM
    """
    # URL локального Ollama (по умолчанию localhost:11434)
    ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/chat')
    ollama_model = getattr(settings, 'OLLAMA_MODEL', 'llama2')
    
    # Если передан user, используем финансовую память
    if user:
        try:
            memory = get_user_financial_memory(user, force_refresh=False)
            if memory:
                sys_prompt = build_system_prompt(memory, extra_context=user_data or "")
            else:
                sys_prompt = settings.LLM_PROMPT_TEMPLATE.format(user_data=user_data or "Нет данных")
        except Exception:
            sys_prompt = settings.LLM_PROMPT_TEMPLATE.format(user_data=user_data or "Нет данных")
    else:
        # Формируем системный промпт
        sys_prompt = settings.LLM_PROMPT_TEMPLATE.format(user_data=user_data or "Нет данных")
    
    # Добавляем системное сообщение
    full_messages = [{"role": "system", "content": sys_prompt}] + messages
    
    payload = {
        "model": ollama_model,
        "messages": full_messages,
        "stream": False
    }
    
    try:
        resp = requests.post(ollama_url, json=payload, timeout=120)
        
        if resp.status_code != 200:
            return f"[Локальная LLM ошибка] HTTP {resp.status_code}. Убедитесь, что Ollama запущен."
        
        data = resp.json()
        if 'message' in data and 'content' in data['message']:
            return data['message']['content']
        elif 'response' in data:
            return data['response']
        else:
            return "[Локальная LLM ошибка] Неожиданный формат ответа."
    except requests.exceptions.ConnectionError:
        return "[Локальная LLM ошибка] Не удалось подключиться к Ollama. Убедитесь, что Ollama запущен на localhost:11434"
    except Exception as ex:
        return f"[Локальная LLM ошибка] {ex}"



def _call_google_gemini(messages: List[Dict[str, str]], sys_prompt: str) -> str:
    """
    Вызывает Google Gemini напрямую через SDK.
    """
    if not genai:
        return "[System Error] google-generativeai package not installed."
        
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # Определяем модель
        current_model = getattr(settings, 'LLM_MODEL', 'gemini-1.5-flash')
        model_name = 'gemini-1.5-flash' # Default safe
        
        # Пытаемся извлечь имя модели, если оно задано в формате provider/model или просто model
        if 'gemini' in current_model.lower():
            if '/' in current_model:
                parts = current_model.split('/')
                # Берем последнюю часть, например 'gemini-2.0-flash-exp'
                model_name = parts[-1]
            else:
                model_name = current_model
                
        # Очистка имени модели от лишних суффиксов (например :free)
        if ':' in model_name:
            model_name = model_name.split(':')[0]
            
        # Initialization
        model = genai.GenerativeModel(model_name, system_instruction=sys_prompt)
        
        # Prepare history
        # Gemini expects history bits as {'role': 'user'|'model', 'parts': [...]}
        gemini_history = []
        
        # Process messages except the last one (which is the new prompt)
        # Note: 'assistant' -> 'model'
        for msg in messages[:-1]:
            role = 'user' if msg['role'] == 'user' else 'model'
            gemini_history.append({'role': role, 'parts': [msg['content']]})
            
        last_msg = messages[-1]['content'] if messages else ""
        
        if not last_msg and not gemini_history:
             return "Пустой запрос."

        chat = model.start_chat(history=gemini_history)
        
        response = chat.send_message(last_msg)
        return response.text
        
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return f"[Gemini API Error] {str(ex)}\n\nУбедитесь, что GOOGLE_API_KEY верен и модель доступна."
