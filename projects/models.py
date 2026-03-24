from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField('Название', max_length=255)
    initiator = models.CharField('Инициатор', max_length=255, blank=True)
    description = models.TextField('Описание / обоснование', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'

    def __str__(self):
        return self.name

    def task_count(self):
        return self.tasks.count()

    def total_hours(self):
        result = self.tasks.aggregate(total=models.Sum('hours'))['total']
        return result or Decimal('0')


class Task(models.Model):
    STATUS_TODO = 'todo'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_DEFERRED = 'deferred'

    STATUS_CHOICES = [
        (STATUS_TODO, 'Запланировано'),
        (STATUS_IN_PROGRESS, 'В работе'),
        (STATUS_DONE, 'Выполнено'),
        (STATUS_DEFERRED, 'Отложено'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    date = models.DateField('Дата')
    task = models.TextField('Задача / описание')
    status = models.CharField(
        'Статус', max_length=20,
        choices=STATUS_CHOICES, default=STATUS_DONE
    )
    initiator = models.CharField('Инициатор задачи', max_length=255, blank=True)
    hours = models.DecimalField(
        'Затраченное время (ч)', max_digits=5, decimal_places=1,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.1'))]
    )
    start_date = models.DateField('Дата начала', null=True, blank=True)
    due_date   = models.DateField('Крайний срок', null=True, blank=True)
    basis = models.TextField('Обоснование', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def __str__(self):
        return f'{self.date} — {self.task[:60]}'

    @property
    def days_until_due(self):
        """Days until due_date. Negative = overdue. None if no due_date."""
        if not self.due_date:
            return None
        from datetime import date
        return (self.due_date - date.today()).days

    @property
    def urgency(self):
        """'overdue' | 'today' | 'soon' (<=3d) | 'upcoming' (<=7d) | None"""
        d = self.days_until_due
        if d is None:
            return None
        if d < 0:
            return 'overdue'
        if d == 0:
            return 'today'
        if d <= 3:
            return 'soon'
        if d <= 7:
            return 'upcoming'
        return None

    @property
    def status_color(self):
        return {
            self.STATUS_TODO: '#6b7280',
            self.STATUS_IN_PROGRESS: '#d97706',
            self.STATUS_DONE: '#059669',
            self.STATUS_DEFERRED: '#dc2626',
        }.get(self.status, '#6b7280')


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='profile', verbose_name='Пользователь'
    )
    last_name  = models.CharField('Фамилия',   max_length=100, blank=True)
    first_name = models.CharField('Имя',        max_length=100, blank=True)
    middle_name= models.CharField('Отчество',   max_length=100, blank=True)
    position   = models.CharField('Должность',  max_length=200, blank=True)
    department = models.CharField('Отдел',      max_length=200, blank=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return self.display_name or self.user.username

    @property
    def display_name(self):
        """Return 'Имя Отчество' if filled, else empty string."""
        parts = [self.first_name, self.middle_name]
        return ' '.join(p for p in parts if p).strip()

    @property
    def full_name(self):
        """Return 'Фамилия Имя Отчество'."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return ' '.join(p for p in parts if p).strip()

    @property
    def initials(self):
        """Return 'ИП' for avatar circle."""
        parts = []
        if self.first_name:
            parts.append(self.first_name[0].upper())
        if self.middle_name:
            parts.append(self.middle_name[0].upper())
        if not parts and self.last_name:
            parts.append(self.last_name[0].upper())
        return ''.join(parts) or self.user.username[:2].upper()


class Conversation(models.Model):
    participants = models.ManyToManyField(
        User, related_name='conversations', verbose_name='Участники'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-created_at']

    def __str__(self):
        names = ', '.join(u.username for u in self.participants.all()[:3])
        return f'Диалог: {names}'

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()

    def last_message(self):
        return self.messages.order_by('-created_at').first()

    def unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages',
        verbose_name='Отправитель'
    )
    text = models.TextField('Текст', blank=True)
    file = models.FileField('Файл', upload_to='chat/%Y/%m/', null=True, blank=True)
    file_name = models.CharField('Имя файла', max_length=255, blank=True)
    file_size = models.PositiveIntegerField('Размер файла', null=True, blank=True)
    file_type = models.CharField('Тип', max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.text[:40]}'
