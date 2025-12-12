import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-me')
DEBUG = True  # Временно включено для отладки

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sb_finance.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sb_finance.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === LLM / AI SETTINGS ===
# Вставьте ваш ключ и эндпоинт в .env или прямо здесь (для демо):
# .env примеры:
# LLM_API_KEY=your_key_here
# LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
# LLM_MODEL=openai/gpt-4o-mini

# ============================================================================
# НАСТРОЙКИ LLM API
# ============================================================================
# ВАЖНО: Вставьте ваш API ключ OpenRouter в .env файл или здесь:
# LLM_API_KEY=sk-or-v1-ваш-ключ-здесь
# 
# Получить ключ можно на https://openrouter.ai/keys
# 
# Доступные модели OpenRouter (от дешевых к дорогим):
# БЕСПЛАТНЫЕ МОДЕЛИ (free tier):
# - deepseek-chat-v3.1:free (рекомендуется: бесплатная, качественная)
# - qwen3-coder-480b-a35b:free (бесплатная, для кода)
# - google/gemini-2.0-flash-exp:free (экспериментальная)
# 
# ПЛАТНЫЕ МОДЕЛИ (от дешевых к дорогим):
# - mistralai/mistral-7b-instruct (самая дешевая, ~$0.10/1M токенов)
# - qwen/qwen-2.5-7b-instruct (очень дешевая, хорошее качество)
# - google/gemini-pro-1.5-flash (дешевая и быстрая, стабильная)
# - openai/gpt-4o-mini (рекомендуется: дешевая и быстрая, ~$0.15/1M токенов)
# - openai/gpt-4o (более мощная, дороже)
# - anthropic/claude-3-haiku (быстрая и качественная)
# 
# Список всех моделей: https://openrouter.ai/models
# ВАЖНО: Для экономии используйте бесплатные модели или модели с меньшим потреблением токенов!
# ============================================================================
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
LLM_API_URL = os.getenv('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
# БЕСПЛАТНАЯ МОДЕЛЬ ПО УМОЛЧАНИЮ
# Можно изменить через переменную окружения LLM_MODEL
LLM_MODEL = os.getenv('LLM_MODEL', 'deepseek-chat-v3.1:free')  # Бесплатная модель по умолчанию

# Авто-коррекция неверных названий моделей
if LLM_MODEL == 'deepseek-chat-v3.1:free':
    LLM_MODEL = 'deepseek/deepseek-r1:free'  # Правильный ID для бесплатной версии DeepSeek R1


# Максимальное количество токенов в ответе (уменьшаем для экономии)
# Рекомендуемые значения: 
# - 2000-3000 для коротких ответов (экономия)
# - 4000 для стандартных ответов
# - 8000+ для детальных анализов (требует больше баланса)
# ВАЖНО: Убедитесь, что max_tokens не превышает ваш доступный баланс на OpenRouter!
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '3000'))

# Дополнительные настройки для OpenRouter
LLM_HTTP_REFERER = os.getenv('LLM_HTTP_REFERER', 'http://localhost:8000')
LLM_APP_TITLE = os.getenv('LLM_APP_TITLE', 'SB Finance AI')
# ============================================================================
# ДИНАМИЧЕСКИЙ ПРОМПТ ДЛЯ LLM
# ============================================================================
# Вы можете настроить этот промпт, чтобы изменить поведение AI.
# Промпт должен содержать {user_data} для вставки данных пользователя.
# ============================================================================
LLM_PROMPT_TEMPLATE = os.getenv('LLM_PROMPT_TEMPLATE', (
    """
Ты — опытный финансовый аналитик и консультант для малого бизнеса.

Твоя задача:
1. Анализировать финансовые транзакции и данные пользователя
2. Находить тренды, аномалии и возможности оптимизации
3. Давать конкретные, actionable советы
4. Делать прогнозы на основе исторических данных
5. Предлагать реальные пути улучшения финансового состояния

ВАЖНЫЕ ТРЕБОВАНИЯ:
- Всегда отвечай в формате Markdown с правильной структурой
- Используй заголовки (##, ###), списки (-, *), таблицы (|), жирный/курсив текст
- Всегда используй ВСЕ доступные данные из файла пользователя для анализа
- Не повторяй ранее данные советы в этой сессии
- Давай уникальные, новые рекомендации каждый раз
- Структурируй ответ: сначала краткая сводка, затем детальный анализ, затем рекомендации

Формат ответа (пример):
## 📊 Анализ финансовых данных

### Ключевые показатели
- Доходы: X руб.
- Расходы: Y руб.
- Прибыль: Z руб.

### Выводы
...

### Рекомендации
1. ...
2. ...

Вот данные пользователя:
{user_data}
"""
))

# ============================================================================
# НАСТРОЙКИ АВТОРИЗАЦИИ
# ============================================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

