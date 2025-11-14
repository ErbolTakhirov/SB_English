from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
import uuid


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self) -> str:
        return self.name


class UserProfile(models.Model):
    """
    Профиль пользователя с поддержкой анонимной регистрации и шифрования.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Анонимная регистрация: seed phrase для восстановления ключа
    seed_phrase = models.TextField(blank=True, null=True, help_text='Seed phrase для восстановления ключа (зашифрован)')
    # Приватный токен для входа без пароля
    private_token = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    # Настройки приватности
    encryption_enabled = models.BooleanField(default=True, help_text='Включено ли шифрование')
    local_mode_only = models.BooleanField(default=False, help_text='Использовать только локальные модели (без облака)')
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    financial_memory = models.JSONField(default=dict, blank=True, help_text='Глобальная финансовая память пользователя')
    success_cases = models.JSONField(default=list, blank=True, help_text='Истории успешных рекомендаций')
    # Настройки импорта файлов
    auto_clear_file_on_import = models.BooleanField(default=False, help_text='Автоматически удалять все транзакции из файла при повторной загрузке')
    auto_remove_duplicates = models.BooleanField(default=False, help_text='Автоматически удалять дублирующиеся строки при импорте')

    def generate_private_token(self):
        """Генерирует приватный токен для входа"""
        self.private_token = uuid.uuid4().hex
        return self.private_token

    def __str__(self):
        return f"Profile for {self.user.username}"


class Income(models.Model):
    # Убрали статичные CATEGORY_CHOICES - теперь категории берутся из БД

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incomes', null=True, blank=True)
    amount = models.FloatField()
    date = models.DateField()
    category = models.CharField(max_length=50)  # Без choices - свободный ввод
    description = models.TextField(blank=True, null=True)
    # Источник файла (если транзакция импортирована из файла)
    source_file = models.ForeignKey('UploadedFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='incomes', help_text='Файл, из которого была импортирована эта транзакция')
    # Зашифрованные данные (если включено шифрование)
    encrypted_data = models.TextField(blank=True, null=True, help_text='Зашифрованные данные (JSON)')
    is_encrypted = models.BooleanField(default=False, help_text='Зашифрованы ли данные')
    tags = models.ManyToManyField(Tag, blank=True, related_name='incomes')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['source_file', 'date', 'amount', 'category']),
        ]

    def __str__(self) -> str:
        return f"Income {self.amount} on {self.date}"


class Expense(models.Model):
    # Убрали статичные CATEGORY_CHOICES - теперь категории берутся из БД

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    amount = models.FloatField()
    date = models.DateField()
    category = models.CharField(max_length=50)  # Без choices - свободный ввод
    description = models.TextField(blank=True, null=True)
    # Источник файла (если транзакция импортирована из файла)
    source_file = models.ForeignKey('UploadedFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses', help_text='Файл, из которого была импортирована эта транзакция')
    # Зашифрованные данные
    encrypted_data = models.TextField(blank=True, null=True, help_text='Зашифрованные данные (JSON)')
    is_encrypted = models.BooleanField(default=False, help_text='Зашифрованы ли данные')
    tags = models.ManyToManyField(Tag, blank=True, related_name='expenses')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['source_file', 'date', 'amount', 'category']),
        ]

    def __str__(self) -> str:
        return f"Expense {self.amount} on {self.date}"


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    date = models.DateField()
    title = models.CharField(max_length=200)
    description = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def __str__(self) -> str:
        return f"Event {self.title} on {self.date}"


class Document(models.Model):
    TYPE_CHOICES = [
        ('contract', 'Договор'),
        ('invoice', 'Счет'),
        ('act', 'Акт'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    doc_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    params = models.JSONField(default=dict)
    generated_text = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='documents')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"Document {self.doc_type} #{self.id}"


class UploadedFile(models.Model):
    """Модель для загруженных пользователем файлов"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # csv, xlsx, pdf, docx
    file_size = models.IntegerField(help_text='Размер файла в байтах')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)  # Дополнительная информация о файле

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['user', 'uploaded_at']),
        ]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.user.username})"


class ChatSession(models.Model):
    """Сессия чата для группировки сообщений с привязкой к пользователю"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True, help_text='Название сессии (автоматически генерируется или задается пользователем)')
    # Файлы, загруженные в рамках данной сессии
    files = models.ManyToManyField('UploadedFile', related_name='chat_sessions', blank=True)
    # Краткие сводки данных по загруженным файлам (для быстрого контекста LLM)
    data_summaries = models.JSONField(default=dict, blank=True, help_text='Краткие сводки по файлам и данным, ключи — file_id или logical name')
    # Кэшированные аналитические сводки/метрики/аггрегации (быстрое отображение при открытии истории)
    analytics_summaries = models.JSONField(default=dict, blank=True, help_text='Кэш сводных метрик/графиков по сессии')
    action_log = models.JSONField(default=dict, blank=True, help_text='Лог советов и статусов действий в рамках сессии')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'updated_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self) -> str:
        if self.user:
            return f"ChatSession {self.session_id} ({self.user.username})"
        return f"ChatSession {self.session_id}"


class ChatMessage(models.Model):
    """Сообщение в чате с хешем для проверки на повторения"""
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'Ассистент'),
        ('system', 'Система'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    # Зашифрованный контент (если включено шифрование)
    encrypted_content = models.TextField(blank=True, null=True, help_text='Зашифрованное содержимое')
    is_encrypted = models.BooleanField(default=False, help_text='Зашифровано ли сообщение')
    content_hash = models.CharField(max_length=64, db_index=True, help_text='SHA256 hash для проверки на повторения')
    metadata = models.JSONField(default=dict, blank=True, help_text='Дополнительные метаданные сообщения (советы, действия, флаги)')
    is_useful = models.BooleanField(default=False, help_text='Отметка пользователя, что совет оказался полезным')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['content_hash']),
        ]
    
    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}..."
