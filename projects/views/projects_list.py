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


# ── Projects list page ────────────────────────────────────

@login_required
def projects_list(request):
    from django.db.models import Q as Q_

    sort = request.GET.get('sort', 'updated')
    search = request.GET.get('search', '').strip()

    projects = Project.objects.filter(user=request.user).annotate(
        task_count_ann=Count('tasks'),
        hours_total=Sum('tasks__hours'),
        done_count=Count('tasks', filter=Q_(tasks__status=Task.STATUS_DONE)),
        todo_count=Count('tasks', filter=Q_(tasks__status=Task.STATUS_TODO)),
        inprog_count=Count('tasks', filter=Q_(tasks__status=Task.STATUS_IN_PROGRESS)),
        deferred_count=Count('tasks', filter=Q_(tasks__status=Task.STATUS_DEFERRED)),
        overdue_count=Count(
            'tasks',
            filter=Q_(tasks__due_date__lt=date.today(), tasks__due_date__isnull=False) &
                   ~Q_(tasks__status=Task.STATUS_DONE)
        ),
    )

    if search:
        projects = projects.filter(
            Q_(name__icontains=search) |
            Q_(initiator__icontains=search) |
            Q_(description__icontains=search)
        )

    if sort == 'name':
        projects = projects.order_by('name')
    elif sort == 'tasks':
        projects = projects.order_by('-task_count_ann')
    elif sort == 'hours':
        projects = projects.order_by('-hours_total')
    elif sort == 'overdue':
        projects = projects.order_by('-overdue_count', '-task_count_ann')
    else:  # updated / default
        projects = projects.order_by('-created_at')

    # Fetch last 3 tasks per project efficiently
    all_project_ids = list(projects.values_list('id', flat=True))
    from django.db.models import Window
    from django.db.models.functions import RowNumber

    recent_tasks_qs = (
        Task.objects
        .filter(project_id__in=all_project_ids)
        .select_related('project')
        .order_by('project_id', '-date', '-created_at')
    )

    # Group manually: last 3 per project
    tasks_by_project = {}
    for task in recent_tasks_qs:
        pid = task.project_id
        if pid not in tasks_by_project:
            tasks_by_project[pid] = []
        if len(tasks_by_project[pid]) < 3:
            tasks_by_project[pid].append(task)

    # Attach to projects
    projects_list_data = []
    for proj in projects:
        proj.recent_tasks_preview = tasks_by_project.get(proj.id, [])
        # Determine card accent color
        if proj.overdue_count > 0:
            proj.accent_color = 'var(--red)'
        elif proj.inprog_count > 0 or proj.todo_count > 0:
            proj.accent_color = 'var(--accent)'
        elif proj.task_count_ann == 0:
            proj.accent_color = 'var(--text3)'
        else:
            proj.accent_color = 'var(--green)'
        projects_list_data.append(proj)

    return render(request, 'projects/projects_list.html', {
        'projects': projects_list_data,
        'sort': sort,
        'search': search,
        'total': len(projects_list_data),
    })