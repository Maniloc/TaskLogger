from django.contrib import admin
from .models import Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'initiator', 'task_count', 'created_at']
    list_filter = ['user']
    search_fields = ['name', 'initiator']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['date', 'project', 'task', 'status', 'hours', 'created_at']
    list_filter = ['project', 'date', 'status']
    search_fields = ['task', 'initiator', 'basis']
