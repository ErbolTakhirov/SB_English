from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone


class UserProfile(models.Model):
    """
    Enhanced user profile for teen-focused FinTech application
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teen_profile')
    
    # Basic teen info
    age = models.PositiveIntegerField(null=True, blank=True)
    bio = models.TextField(blank=True, null=True, help_text='Short bio or occupation')
    timezone = models.CharField(max_length=50, default='Asia/Bishkek')
    
    # Financial settings
    monthly_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='KGS')  # Kyrgyz Som by default
    
    # Gamification
    financial_iq_score = models.PositiveIntegerField(default=0, help_text='0-100 score based on learning progress')
    total_achievements = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0, help_text='Consecutive days using app')
    longest_streak = models.PositiveIntegerField(default=0)
    
    # Learning progress
    lessons_completed = models.PositiveIntegerField(default=0)
    quizzes_passed = models.PositiveIntegerField(default=0)
    goals_achieved = models.PositiveIntegerField(default=0)
    
    # Privacy and preferences
    preferred_language = models.CharField(max_length=5, default='ru', choices=[
        ('ru', 'Русский'),
        ('en', 'English'),
        ('ky', 'Кыргызча')
    ])
    demo_mode = models.BooleanField(default=False, help_text='Enable demo data for presentations')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username} (IQ: {self.financial_iq_score})"


class UserGoal(models.Model):
    """
    Teen-friendly savings goals with timelines and progress tracking
    """
    CATEGORY_CHOICES = [
        ('electronics', 'Электроника'),
        ('fashion', 'Одежда'),
        ('education', 'Образование'),
        ('entertainment', 'Развлечения'),
        ('travel', 'Путешествия'),
        ('other', 'Другое')
    ]
    
    STATUS_CHOICES = [
        ('active', 'Активная'),
        ('completed', 'Достигнута'),
        ('paused', 'Приостановлена'),
        ('cancelled', 'Отменена')
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200, help_text='Цель (например: "Новый iPhone 15")')
    description = models.TextField(blank=True, help_text='Дополнительное описание')
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Целевая сумма')
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Накоплено')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Timeline
    target_date = models.DateField(help_text='Желаемая дата достижения')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # AI insights
    ai_recommendation = models.TextField(blank=True, help_text='AI совет по достижению цели')
    weekly_saving_suggestion = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    def progress_percentage(self):
        """Calculate progress as percentage"""
        if self.target_amount == 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)
    
    def days_remaining(self):
        """Days remaining to target date"""
        if self.status != 'active':
            return 0
        delta = self.target_date - timezone.now().date()
        return max(0, delta.days)
    
    def weekly_target(self):
        """Recommended weekly saving amount"""
        days = self.days_remaining()
        if days <= 0:
            return 0
        remaining = self.target_amount - self.current_amount
        weeks = days / 7
        return remaining / weeks if weeks > 0 else 0
    
    def __str__(self):
        return f"{self.title} - {self.current_amount}/{self.target_amount} ({self.progress_percentage():.0f}%)"


class LearningModule(models.Model):
    """
    Financial education content for teens
    """
    DIFFICULTY_CHOICES = [
        ('beginner', 'Начинающий'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый')
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    content = models.TextField(help_text='HTML content for the lesson')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    estimated_time = models.PositiveIntegerField(help_text='Estimated time in minutes')
    
    # Learning objectives
    learning_objectives = models.JSONField(default=list, help_text='List of learning objectives')
    
    # SEO and categorization
    category = models.CharField(max_length=50, help_text='Topic category')
    tags = models.JSONField(default=list, help_text='Related tags')
    
    # AI-generated content
    ai_summary = models.TextField(blank=True, help_text='AI-generated lesson summary')
    real_world_examples = models.JSONField(default=list, help_text='Examples relevant to teen life')
    
    # Publishing
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['difficulty', 'created_at']
    
    def __str__(self):
        return f"{self.title} ({self.difficulty})"


class Quiz(models.Model):
    """
    Interactive quizzes for learning reinforcement
    """
    module = models.ForeignKey(LearningModule, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    questions_count = models.PositiveIntegerField(default=0)
    passing_score = models.PositiveIntegerField(default=70, help_text='Minimum score to pass (%)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Quiz: {self.title}"


class QuizQuestion(models.Model):
    """
    Individual quiz questions with multiple choice answers
    """
    QUESTION_TYPE_CHOICES = [
        ('multiple_choice', 'Множественный выбор'),
        ('true_false', 'Верно/Неверно'),
        ('fill_blank', 'Заполнить пропуск')
    ]
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='multiple_choice')
    
    # For multiple choice
    option_a = models.CharField(max_length=200, blank=True)
    option_b = models.CharField(max_length=200, blank=True)
    option_c = models.CharField(max_length=200, blank=True)
    option_d = models.CharField(max_length=200, blank=True)
    
    correct_answer = models.CharField(max_length=5, help_text='A, B, C, D, or True/False')
    explanation = models.TextField(help_text='Explanation of the correct answer')
    
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Q: {self.question_text[:50]}..."


class UserQuizAttempt(models.Model):
    """
    Track user quiz attempts and results
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(help_text='Score achieved (%)')
    passed = models.BooleanField(help_text='Whether user passed the quiz')
    answers = models.JSONField(help_text='User answers to questions')
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-completed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score}%"


class Achievement(models.Model):
    """
    Achievement badges for gamification
    """
    CATEGORY_CHOICES = [
        ('budgeting', 'Бюджетирование'),
        ('saving', 'Накопления'),
        ('learning', 'Обучение'),
        ('streak', 'Активность'),
        ('security', 'Безопасность'),
        ('milestone', 'Вехи')
    ]
    
    title = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    icon = models.CharField(max_length=50, help_text='Icon name or emoji')
    
    # Achievement criteria (stored as JSON for flexibility)
    criteria = models.JSONField(help_text='Conditions to unlock this achievement')
    
    # Points and rewards
    points = models.PositiveIntegerField(default=10, help_text='Points awarded for this achievement')
    iq_bonus = models.PositiveIntegerField(default=1, help_text='Financial IQ points bonus')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.points} pts)"


class UserAchievement(models.Model):
    """
    Track user achievements and unlock dates
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    progress = models.JSONField(default=dict, help_text='Current progress toward achievement')
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.achievement.title}"


class FinancialInsight(models.Model):
    """
    AI-generated financial insights and diary entries
    """
    INSIGHT_TYPE_CHOICES = [
        ('daily_summary', 'Дневная сводка'),
        ('weekly_report', 'Недельный отчет'),
        ('spending_pattern', 'Паттерн трат'),
        ('savings_tip', 'Совет по накоплениям'),
        ('goal_progress', 'Прогресс по цели'),
        ('behavior_analysis', 'Анализ поведения')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='financial_insights')
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    content = models.TextField(help_text='AI-generated insight content')
    
    # Data used for generation
    source_data = models.JSONField(default=dict, help_text='Data used to generate this insight')
    
    # User interaction
    is_read = models.BooleanField(default=False)
    user_rating = models.PositiveIntegerField(null=True, blank=True, help_text='1-5 star rating')
    feedback = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.insight_type}: {self.title}"


class ScamAlert(models.Model):
    """
    Scam awareness and detection module
    """
    SEVERITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scam_alerts', null=True, blank=True)
    
    # Reported content
    reported_text = models.TextField(help_text='Text user wants to check for scams')
    reported_url = models.URLField(blank=True, help_text='URL if provided')
    
    # AI Analysis
    is_suspicious = models.BooleanField(help_text='Whether AI detected scam indicators')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    risk_score = models.PositiveIntegerField(help_text='Risk score 0-100')
    
    # Explanation
    red_flags = models.JSONField(default=list, help_text='List of identified red flags')
    explanation = models.TextField(help_text='AI explanation of why this is suspicious')
    safe_alternatives = models.JSONField(default=list, help_text='Safe alternatives or advice')
    
    # User interaction
    user_agrees = models.BooleanField(null=True, blank=True, help_text='Whether user agrees with AI assessment')
    report_submitted = models.BooleanField(default=False, help_text='Whether user reported this to authorities')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Scam Alert: {self.severity} ({self.risk_score}% risk)"


class UserProgress(models.Model):
    """
    Track user learning and engagement progress
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='progress')
    
    # Learning metrics
    modules_started = models.PositiveIntegerField(default=0)
    modules_completed = models.PositiveIntegerField(default=0)
    total_study_time = models.PositiveIntegerField(default=0, help_text='Total study time in minutes')
    
    # Financial metrics
    budgets_created = models.PositiveIntegerField(default=0)
    goals_created = models.PositiveIntegerField(default=0)
    goals_achieved = models.PositiveIntegerField(default=0)
    
    # Engagement metrics
    ai_conversations = models.PositiveIntegerField(default=0)
    insights_generated = models.PositiveIntegerField(default=0)
    streak_days = models.PositiveIntegerField(default=0)
    
    # Last activity
    last_activity = models.DateTimeField(auto_now=True)
    last_lesson_date = models.DateTimeField(null=True, blank=True)
    last_goal_update = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Progress for {self.user.username}"


# Update existing models with teen-specific enhancements
class Income(models.Model):
    """Enhanced income model for teen finances"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teen_incomes')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    
    # Teen-friendly categories
    income_type = models.CharField(max_length=50, choices=[
        ('allowance', 'Карманные деньги'),
        ('part_time', 'Подработка'),
        ('gift', 'Подарок'),
        ('freelance', 'Фриланс'),
        ('sales', 'Продажи'),
        ('investment', 'Инвестиции'),
        ('services', 'Услуги'),
        ('salary', 'Зарплата'),
        ('bonus', 'Бонус'),
        ('other', 'Другое')
    ], default='other')
    
    description = models.TextField(blank=True, null=True)
    merchant = models.CharField(max_length=255, blank=True, null=True, help_text='Sender or business name')
    source = models.CharField(max_length=100, blank=True, help_text='Source of income (e.g., parents, employer)')
    source_file = models.ForeignKey('UploadedFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='incomes')
    
    # AI and Review
    needs_review = models.BooleanField(default=False)
    ai_category_confidence = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='KGS')
    
    # Goal linking
    linked_goal = models.ForeignKey(UserGoal, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='contributions', help_text='Goal this income contributes to')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['source_file']),
        ]

    def __str__(self):
        return f"{self.income_type}: {self.amount} on {self.date}"


class Expense(models.Model):
    """Enhanced expense model for teen spending"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teen_expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    
    # Teen-friendly categories
    expense_type = models.CharField(max_length=50, choices=[
        ('food', 'Еда'),
        ('transport', 'Транспорт'),
        ('entertainment', 'Развлечения'),
        ('shopping', 'Покупки'),
        ('subscriptions', 'Подписки'),
        ('education', 'Образование'),
        ('health', 'Здоровье'),
        ('beauty', 'Красота'),
        ('games', 'Игры'),
        ('rent', 'Аренда'),
        ('marketing', 'Маркетинг'),
        ('software', 'ПО/Сервисы'),
        ('equipment', 'Оборудование'),
        ('tax', 'Налоги'),
        ('other', 'Другое')
    ], default='other')
    
    description = models.TextField(blank=True, null=True)
    merchant = models.CharField(max_length=255, blank=True, null=True, help_text='Store or merchant name')
    is_essential = models.BooleanField(default=False, help_text='Is this an essential expense?')
    source_file = models.ForeignKey('UploadedFile', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    
    # AI and Review
    needs_review = models.BooleanField(default=False)
    ai_category_confidence = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='KGS')

    # Goal impact
    impacts_goal = models.ForeignKey(UserGoal, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text='Goal this expense affects')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['source_file']),
        ]
    
    def __str__(self):
        return f"{self.expense_type}: {self.amount} on {self.date}"


# Enhanced chat system for teen AI coach
class TeenChatSession(models.Model):
    """Chat sessions specifically for teen financial coaching"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teen_chat_sessions')
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    
    # Context for teen-specific coaching
    conversation_context = models.JSONField(default=dict, help_text='Context like age, goals, current situation')
    mood = models.CharField(max_length=20, blank=True, help_text='User mood during conversation')
    
    # AI coaching specifics
    coaching_focus = models.CharField(max_length=50, blank=True, help_text='Main focus of this coaching session')
    educational_content_shared = models.BooleanField(default=False, help_text='Whether educational content was shared')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Teen Coach: {self.title or self.session_id}"


class TeenChatMessage(models.Model):
    """Messages in teen coaching chat with enhanced features"""
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('teen_coach', 'AI Коуч'),
        ('system', 'Система')
    ]
    
    session = models.ForeignKey(TeenChatSession, on_delete=models.CASCADE, related_name='teen_messages')
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # Educational features
    is_educational = models.BooleanField(default=False, help_text='Contains educational content')
    learning_objective = models.CharField(max_length=200, blank=True, help_text='Learning objective of this message')
    
    # AI coaching metadata
    confidence_score = models.PositiveIntegerField(null=True, blank=True, help_text='AI confidence in response (0-100)')
    reasoning_explained = models.TextField(blank=True, help_text='Why AI gave this advice')
    
    # User interaction
    user_reaction = models.CharField(max_length=20, blank=True, help_text='User reaction (helpful, confusing, etc.)')
    was_actionable = models.BooleanField(default=False, help_text='Whether this message contained actionable advice')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


# Legacy models for backward compatibility
class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self) -> str:
        return self.name


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
    """Model for uploaded files"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # csv, xlsx, pdf, docx
    file_size = models.IntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['user', 'uploaded_at']),
        ]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.user.username})"


class ChatSession(models.Model):
    """Legacy chat session for backward compatibility"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    files = models.ManyToManyField('UploadedFile', related_name='chat_sessions', blank=True)
    data_summaries = models.JSONField(default=dict, blank=True)
    analytics_summaries = models.JSONField(default=dict, blank=True)
    action_log = models.JSONField(default=dict, blank=True)
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
    """Legacy chat message for backward compatibility"""
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'Ассистент'),
        ('system', 'Система'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    encrypted_content = models.TextField(blank=True, null=True)
    is_encrypted = models.BooleanField(default=False)
    content_hash = models.CharField(max_length=64, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_useful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['content_hash']),
        ]
    
    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}..."
