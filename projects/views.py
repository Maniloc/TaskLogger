import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.conf import settings
from datetime import date
from decimal import Decimal, InvalidOperation
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from .models import Project, Task

logger = logging.getLogger(__name__)


# ── Dashboard ─────────────────────────────────────────────

@login_required
def index(request):
    projects = Project.objects.filter(user=request.user).annotate(
        task_count_ann=Count('tasks'),
        hours_total=Sum('tasks__hours'),
    )
    today = date.today()
    month_start = today.replace(day=1)
    recent_tasks = Task.objects.filter(
        project__user=request.user,
        date__gte=month_start,
    ).select_related('project').order_by('-date')[:5]

    agg = Task.objects.filter(
        project__user=request.user,
        date__gte=month_start,
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    return render(request, 'projects/index.html', {
        'projects': projects,
        'recent_tasks': recent_tasks,
        'tasks_count': agg['count'] or 0,
        'tasks_hours': agg['hours'] or Decimal('0'),
        'today': today,
    })


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
    })


# ── Tasks ─────────────────────────────────────────────────

def _parse_hours(raw):
    """Parse hours from user input. Accepts '2.5', '2,5', '2h30m', '2ч30м', '2:30'."""
    if not raw:
        return None
    raw = raw.strip().lower()

    # formats: "2ч30м", "2h30m", "2:30"
    import re
    m = re.match(r'^(\d+)[hч][:\s]*(\d+)[mм]?$', raw)
    if m:
        return Decimal(m.group(1)) + Decimal(m.group(2)) / 60

    m = re.match(r'^(\d+):(\d+)$', raw)
    if m:
        return Decimal(m.group(1)) + Decimal(m.group(2)) / 60

    # plain number
    try:
        return Decimal(raw.replace(',', '.'))
    except InvalidOperation:
        raise ValueError(f'Неверный формат: «{raw}». Примеры: 2.5, 2ч30м, 2:30')


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
            basis=request.POST.get('basis', '').strip(),
        )
        messages.success(request, f'Задача добавлена в «{project.name}»')
        next_url = request.POST.get('next', '/')
        return redirect(next_url)

    return render(request, 'projects/quick_add.html', {
        'projects': projects,
        'status_choices': Task.STATUS_CHOICES,
    })


# ── Report ────────────────────────────────────────────────

@login_required
def report(request):
    projects = Project.objects.filter(user=request.user)
    tasks = Task.objects.filter(
        project__user=request.user
    ).select_related('project')

    today = date.today()
    date_from = request.GET.get('date_from', today.replace(day=1).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    project_id = request.GET.get('project', '')
    group_by = request.GET.get('group_by', 'project')

    if date_from:
        tasks = tasks.filter(date__gte=date_from)
    if date_to:
        tasks = tasks.filter(date__lte=date_to)
    if project_id:
        tasks = tasks.filter(project_id=project_id)

    tasks = tasks.order_by('date', 'project__name')

    # Materialise once — avoid double-hit in xlsx path
    tasks_list = list(tasks)
    total_hours = sum(
        (t.hours for t in tasks_list if t.hours), Decimal('0')
    )

    if request.GET.get('export') == 'xlsx':
        return _export_xlsx(tasks_list, date_from, date_to)

    grouped = _group_tasks(tasks_list, group_by)

    return render(request, 'projects/report.html', {
        'projects': projects,
        'tasks': tasks_list,
        'grouped': grouped,
        'group_by': group_by,
        'date_from': date_from,
        'date_to': date_to,
        'project_id': project_id,
        'selected_project': projects.filter(pk=project_id).first() if project_id else None,
        'total': len(tasks_list),
        'total_hours': total_hours,
    })


def _group_tasks(tasks_list, group_by):
    grouped = {}
    if group_by == 'project':
        for t in tasks_list:
            grouped.setdefault(t.project, []).append(t)
    elif group_by == 'date':
        for t in tasks_list:
            grouped.setdefault(t.date, []).append(t)
    else:
        grouped = {'__all__': tasks_list}
    return grouped


def _export_xlsx(tasks_list, date_from, date_to):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Отчёт'

    hf = Font(bold=True, color='FFFFFF', size=11)
    hfill = PatternFill(start_color='1C1C1A', end_color='1C1C1A', fill_type='solid')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap = Alignment(wrap_text=True, vertical='top')
    even_fill = PatternFill(start_color='F5F5F3', end_color='F5F5F3', fill_type='solid')

    headers = ['Дата', 'Проект', 'Задача', 'Статус', 'Инициатор', 'Часы', 'Обоснование']
    widths = [12, 24, 50, 16, 24, 8, 40]

    ws.row_dimensions[1].height = 22
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = hf
        c.fill = hfill
        c.alignment = center
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    status_map = dict(Task.STATUS_CHOICES)
    total_hours = Decimal('0')

    for ri, task in enumerate(tasks_list, 2):
        h = task.hours or None
        if h:
            total_hours += h
        row = [
            task.date.strftime('%d.%m.%Y'),
            task.project.name,
            task.task,
            status_map.get(task.status, task.status),
            task.initiator or '—',
            float(h) if h else '—',
            task.basis or '—',
        ]
        ws.row_dimensions[ri].height = 40
        for ci, val in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.alignment = wrap
            if ri % 2 == 0:
                c.fill = even_fill

    # Summary
    sr = len(tasks_list) + 2
    ws.cell(row=sr, column=1, value='Итого').font = Font(bold=True)
    ws.cell(row=sr, column=6, value=float(total_hours)).font = Font(bold=True)

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:G{len(tasks_list) + 1}'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    period = f'{date_from}__{date_to}' if (date_from or date_to) else 'all'
    response['Content-Disposition'] = f'attachment; filename="report_{period}.xlsx"'
    wb.save(response)
    return response
