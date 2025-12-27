import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-me')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Render Deployment: Allow all hosts initially to prevent initialization validation errors
# Render Deployment: Allow all hosts initially to prevent initialization validation errors
ALLOWED_HOSTS = ["*"]

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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
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

# Production database (PostgreSQL on Render)
if os.getenv('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
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
# LLM_API_KEY=your-key-here
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
**CRITICAL: You MUST respond ONLY in English. Never use Russian or any other language.**

You are an experienced financial analyst and consultant for small businesses.

Your task:
1. Analyze financial transactions and user data
2. Find trends, anomalies, and optimization opportunities
3. Give specific, actionable advice
4. Make forecasts based on historical data
5. Suggest real ways to improve financial health

IMPORTANT REQUIREMENTS:
- Always answer in Markdown format with proper structure
- Use headers (##, ###), lists (-, *), tables (|), bold/italic text
- Always use ALL available data from the user's file for analysis
- Do not repeat previously given advice in this session
- Provide unique, new recommendations every time
- Structure the answer: first a brief summary, then detailed analysis, then recommendations

Response Format (example):
## 📊 Financial Data Analysis

### Key Metrics
- Income: X
- Expenses: Y
- Profit: Z

### Conclusions
...

### Recommendations
1. ...
2. ...

Here is the user data:
{user_data}
"""
))

# ============================================================================
# НАСТРОЙКИ АВТОРИЗАЦИИ
# ============================================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Unique cookie names to avoid clashes with other projects on 127.0.0.1
CSRF_COOKIE_NAME = 'sb_finance_csrftoken'
SESSION_COOKIE_NAME = 'sb_finance_sessionid'

# Trusted origins for CSRF (useful when running on non-standard ports)
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8001',
    'http://localhost:8000',
    'http://localhost:8001',
]

# ============================================================================
# TEEN FINANCE AI - FinBilim 2025 Hackathon Settings
# ============================================================================

# LLM Configuration for Teen AI Coach
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openrouter')
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_MODEL = os.getenv('LLM_MODEL', 'openai/gpt-4o-mini')
LLM_API_URL = os.getenv('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
LLM_HTTP_REFERER = os.getenv('LLM_HTTP_REFERER', 'http://localhost:8000')

# Teen-specific features
TEEN_EDUCATION_ENABLED = True
TEEN_GAMIFICATION_ENABLED = True
TEEN_SCAM_PROTECTION_ENABLED = True
TEEN_DEMO_MODE_DEFAULT = False

# Financial education content settings
LEARNING_MODULES_PUBLISH_AUTO = True
QUIZ_PASSING_SCORE_DEFAULT = 70
MAX_QUIZ_ATTEMPTS = 3

# Gamification settings
ACHIEVEMENT_POINTS_ENABLED = True
FINANCIAL_IQ_MAX_SCORE = 100
STREAK_REWARD_THRESHOLD = 7

# Security and privacy
TEEN_DATA_PROTECTION = True
AUTO_ANONYMIZE_CHAT_DATA = True
SCAM_REPORT_RETENTION_DAYS = 90

# Demo mode settings
DEMO_USER_BALANCE = 5000
DEMO_GOALS_SAMPLE_SIZE = 3
DEMO_ACHIEVEMENTS_SAMPLE_SIZE = 5

