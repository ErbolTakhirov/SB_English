"""
Модель для финансовых целей пользователя.
Позволяет отслеживать прогресс достижения целей и давать рекомендации.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from datetime import date


class FinancialGoal(models.Model):
    """
    Финансовая цель пользователя (накопления, инвестиции, погашение долга).
    """
    
    GOAL_TYPES = [
        ('savings', 'Накопления'),
        ('investment', 'Инвестиции'),
        ('debt_payment', 'Погашение долга'),
        ('purchase', 'Покупка'),
        ('emergency_fund', 'Резервный фонд'),
        ('other', 'Другое'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Активная'),
        ('completed', 'Выполнена'),
        ('paused', 'На паузе'),
        ('cancelled', 'Отменена'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='financial_goals'
    )
    
    title = models.CharField(
        max_length=200,
        help_text='Название цели, например "Покупка ноутбука"'
    )
    
    description = models.TextField(
        blank=True,
        help_text='Подробное описание цели'
    )
    
    goal_type = models.CharField(
        max_length=20,
        choices=GOAL_TYPES,
        default='savings'
    )
    
    target_amount = models.FloatField(
        validators=[MinValueValidator(0.01)],
        help_text='Целевая сумма'
    )
    
    current_amount = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Текущая накопленная сумма'
    )
    
    deadline = models.DateField(
        help_text='Срок достижения цели'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    monthly_contribution = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Ежемесячный взнос (рекомендуемый или фактический)'
    )
    
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text='Категория для связи с расходами/доходами'
    )
    
    priority = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Приоритет (1-10, где 10 - наивысший)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Метаданные для аналитики
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Дополнительные данные (история взносов, заметки)'
    )
    
    class Meta:
        ordering = ['-priority', 'deadline', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['deadline']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_progress_percentage()}%)"
    
    def get_progress_percentage(self):
        """Возвращает процент выполнения цели"""
        if self.target_amount <= 0:
            return 0
        progress = (self.current_amount / self.target_amount) * 100
        return min(round(progress, 2), 100)
    
    def get_remaining_amount(self):
        """Возвращает оставшуюся сумму до цели"""
        return max(0, self.target_amount - self.current_amount)
    
    def get_days_remaining(self):
        """Возвращает количество дней до дедлайна"""
        if self.deadline < date.today():
            return 0
        delta = self.deadline - date.today()
        return delta.days
    
    def get_months_remaining(self):
        """Возвращает количество месяцев до дедлайна"""
        days = self.get_days_remaining()
        return max(1, days // 30)
    
    def get_required_monthly_contribution(self):
        """Вычисляет необходимый ежемесячный взнос для достижения цели"""
        remaining = self.get_remaining_amount()
        months = self.get_months_remaining()
        return round(remaining / months, 2) if months > 0 else remaining
    
    def is_on_track(self):
        """Проверяет, идет ли цель по плану"""
        required = self.get_required_monthly_contribution()
        return self.monthly_contribution >= required if self.monthly_contribution > 0 else None
    
    def update_progress(self, amount):
        """Обновляет прогресс цели"""
        self.current_amount += amount
        
        # Обновляем историю взносов
        history = self.metadata.get('contribution_history', [])
        history.append({
            'amount': amount,
            'date': date.today().isoformat(),
            'current_total': self.current_amount
        })
        self.metadata['contribution_history'] = history
        
        # Проверяем выполнение
        if self.current_amount >= self.target_amount:
            self.status = 'completed'
            from django.utils import timezone
            self.completed_at = timezone.now()
        
        self.save()
    
    def get_recommendation(self):
        """Возвращает рекомендацию по достижению цели"""
        required = self.get_required_monthly_contribution()
        current = self.monthly_contribution
        days = self.get_days_remaining()
        
        if self.status == 'completed':
            return "🎉 Поздравляем! Цель достигнута!"
        
        if days <= 0:
            return "⚠️ Дедлайн истек! Продлите срок или увеличьте взносы."
        
        if current <= 0:
            return f"💡 Начните откладывать {required:,.0f} руб/месяц для достижения цели."
        
        if current < required:
            deficit = required - current
            return f"⚠️ Увеличьте взносы на {deficit:,.0f} руб/месяц (с {current:,.0f} до {required:,.0f})"
        
        if current >= required:
            surplus = current - required
            return f"✅ Отлично! Вы опережаете план на {surplus:,.0f} руб/месяц"
        
        return "📊 Следуйте текущему плану взносов"


class GoalMilestone(models.Model):
    """
    Промежуточные вехи для финансовых целей.
    """
    goal = models.ForeignKey(
        FinancialGoal,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    
    title = models.CharField(max_length=200)
    target_amount = models.FloatField()
    target_date = models.DateField()
    achieved = models.BooleanField(default=False)
    achieved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['target_date']
    
    def __str__(self):
        return f"{self.goal.title} - {self.title}"
