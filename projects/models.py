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
    basis = models.TextField('Обоснование', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def __str__(self):
        return f'{self.date} — {self.task[:60]}'

    @property
    def status_color(self):
        return {
            self.STATUS_TODO: '#6b7280',
            self.STATUS_IN_PROGRESS: '#d97706',
            self.STATUS_DONE: '#059669',
            self.STATUS_DEFERRED: '#dc2626',
        }.get(self.status, '#6b7280')
