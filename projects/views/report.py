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