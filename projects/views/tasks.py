from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Case, When, Value, IntegerField
from django.http import HttpResponse
from django.conf import settings
from datetime import date, timedelta
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from ..models import Project, Task
from .utils import _jdumps, _parse_hours, superuser_required


# ── Tasks ─────────────────────────────────────────────────

@login_required
@require_POST
def task_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, user=request.user)
    task_text = request.POST.get('task', '').strip()
    task_date = request.POST.get('date', '')

    if not task_text or not task_date:
        messages.error(request, 'Заполните дату и описание задачи')
        return redirect('project_detail', pk=project_pk)

    try:
        hours = _parse_hours(request.POST.get('hours', ''))
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('project_detail', pk=project_pk)

    Task.objects.create(
        project=project,
        date=task_date,
        task=task_text,
        status=request.POST.get('status', Task.STATUS_DONE),
        initiator=request.POST.get('initiator', '').strip(),
        hours=hours,
        start_date = request.POST.get('start_date', '').strip() or None,
        due_date   = request.POST.get('due_date', '').strip() or None,
        basis=request.POST.get('basis', '').strip(),
    )
    messages.success(request, 'Задача добавлена')
    return redirect('project_detail', pk=project_pk)


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, project__user=request.user)
    project_pk = task.project_id
    task.delete()
    messages.success(request, 'Задача удалена')
    return redirect('project_detail', pk=project_pk)


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, project__user=request.user)

    if request.method == 'POST':
        task_text = request.POST.get('task', '').strip()
        if not task_text:
            messages.error(request, 'Описание задачи не может быть пустым')
            return render(request, 'projects/task_edit.html', {
                'task': task, 'status_choices': Task.STATUS_CHOICES
            })
        try:
            hours = _parse_hours(request.POST.get('hours', ''))
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'projects/task_edit.html', {
                'task': task, 'status_choices': Task.STATUS_CHOICES
            })

        task.date = request.POST.get('date', task.date)
        task.task = task_text
        task.status = request.POST.get('status', task.status)
        task.initiator = request.POST.get('initiator', '').strip()
        task.hours = hours
        task.start_date = request.POST.get('start_date', '').strip() or None
        task.due_date   = request.POST.get('due_date', '').strip() or None
        task.basis = request.POST.get('basis', '').strip()
        task.save()
        messages.success(request, 'Задача обновлена')
        return redirect('project_detail', pk=task.project_id)

    return render(request, 'projects/task_edit.html', {
        'task': task,
        'status_choices': Task.STATUS_CHOICES,
    })

# ── Quick task (navbar shortcut) ──────────────────────────

@login_required
def quick_add(request):
    """Quick-add task from any page via navbar button."""
    projects = Project.objects.filter(user=request.user)
    if request.method == 'POST':
        project_pk = request.POST.get('project_id', '')
        task_text = request.POST.get('task', '').strip()
        task_date = request.POST.get('date', '')
        if not project_pk or not task_text or not task_date:
            messages.error(request, 'Заполните проект, дату и описание')
            return render(request, 'projects/quick_add.html', {
                'projects': projects,
                'status_choices': Task.STATUS_CHOICES,
            })
        project = get_object_or_404(Project, pk=project_pk, user=request.user)
        try:
            hours = _parse_hours(request.POST.get('hours', ''))
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'projects/quick_add.html', {
                'projects': projects,
                'status_choices': Task.STATUS_CHOICES,
            })
        Task.objects.create(
            project=project,
            date=task_date,
            task=task_text,
            status=request.POST.get('status', Task.STATUS_DONE),
            initiator=request.POST.get('initiator', '').strip(),
            hours=hours,
        start_date = request.POST.get('start_date', '').strip() or None,
        due_date   = request.POST.get('due_date', '').strip() or None,
            basis=request.POST.get('basis', '').strip(),
        )
        messages.success(request, f'Задача добавлена в «{project.name}»')
        next_url = request.POST.get('next', '/')
        return redirect(next_url)

    return render(request, 'projects/quick_add.html', {
        'projects': projects,
        'status_choices': Task.STATUS_CHOICES,
    })