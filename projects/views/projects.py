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


# ── Projects ──────────────────────────────────────────────

@login_required
@require_POST
def project_create(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Введите название проекта')
        return redirect('index')
    Project.objects.create(
        user=request.user,
        name=name,
        initiator=request.POST.get('initiator', '').strip(),
        description=request.POST.get('description', '').strip(),
    )
    messages.success(request, f'Проект «{name}» создан')
    return redirect('index')


@login_required
@require_POST
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    task_count = project.tasks.count()
    name = project.name
    project.delete()
    messages.success(request, f'Проект «{name}» и {task_count} задач удалены')
    return redirect('index')


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    tasks = project.tasks.select_related('project').all()

    month = request.GET.get('month', '')
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if month:
        tasks = tasks.filter(date__startswith=month)
    if search:
        tasks = tasks.filter(
            Q(task__icontains=search) |
            Q(initiator__icontains=search) |
            Q(basis__icontains=search)
        )
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    total_hours = tasks.aggregate(total=Sum('hours'))['total'] or Decimal('0')
    paginator = Paginator(tasks, getattr(settings, 'TASKS_PER_PAGE', 25))
    page_obj = paginator.get_page(request.GET.get('page'))

    from ..models import ProjectMember as _PM
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'page_obj': page_obj,
        'tasks': page_obj,
        'month': month,
        'search': search,
        'status_filter': status_filter,
        'total_hours': total_hours,
        'status_choices': Task.STATUS_CHOICES,
        'project_total_hours': project.total_hours(),
        'member_count':        _PM.objects.filter(project=project).count(),
        'project_members_list': _PM.objects.filter(project=project).select_related('user','user__profile'),
    })


@login_required
@require_POST
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Название проекта не может быть пустым')
        return redirect('project_detail', pk=pk)
    project.name = name
    project.initiator = request.POST.get('initiator', '').strip()
    project.description = request.POST.get('description', '').strip()
    project.save()
    messages.success(request, f'Проект «{project.name}» обновлён')
    return redirect('project_detail', pk=pk)