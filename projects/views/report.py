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
        # If user is a member (not owner) of this project — show only own tasks
        from ..models import ProjectMember as _PM
        proj = Project.objects.filter(pk=project_id).first()
        if proj and proj.user != request.user:
            m = _PM.objects.filter(project_id=project_id, user=request.user).first()
            if m:  # participant: show only own tasks
                tasks = tasks.filter(
                    __import__('django.db.models', fromlist=['Q']).Q(assigned_to=request.user) |
                    __import__('django.db.models', fromlist=['Q']).Q(assigned_to__isnull=True,
                        project__user=request.user)
                )

    tasks = tasks.order_by('date', 'project__name')

    # Materialise once — avoid double-hit in xlsx path
    tasks_list = list(tasks)
    total_hours = sum(
        (t.hours for t in tasks_list if t.hours), Decimal('0')
    )

    if request.GET.get('export') == 'xlsx' or request.GET.get('format') == 'xlsx':
        return _export_xlsx(tasks_list, date_from, date_to)

    grouped = _group_tasks(tasks_list, group_by)

    # Build text report for copy-paste
    status_map = dict(Task.STATUS_CHOICES)
    text_lines = []
    current_proj = None
    for t in tasks_list:
        if t.project != current_proj:
            current_proj = t.project
            text_lines.append(f'\n{t.project.name}')
            text_lines.append('─' * len(t.project.name))
        hours_str = f' [{t.hours}ч]' if t.hours else ''
        text_lines.append(f'{t.date.strftime("%d.%m.%Y")}{hours_str} — {t.task}')
        if t.basis:
            text_lines.append(f'  Обоснование: {t.basis}')
    text_report = '\n'.join(text_lines).strip()

    return render(request, 'projects/report.html', {
        'projects': projects,
        'tasks': tasks_list,
        'grouped': grouped,
        'group_by': group_by,
        'date_from': date_from,
        'date_to': date_to,
        'status_filter': request.GET.get('status', ''),
        'status_choices': Task.STATUS_CHOICES,
        'selected_project': str(project_id) if project_id else '',
        'total': len(tasks_list),
        'total_hours': total_hours,
        'text_report': text_report,
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
    from openpyxl.styles import Border, Side, GradientFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Отчёт'

    # ── Design tokens ──
    COLOR_ACCENT     = '1E40AF'   # deep blue for header
    COLOR_ACCENT_LIGHT = 'DBEAFE' # light blue for accents
    COLOR_ROW_ODD    = 'FFFFFF'
    COLOR_ROW_EVEN   = 'F8FAFF'   # very light blue tint
    COLOR_TOTAL_BG   = 'EFF6FF'
    COLOR_DONE       = '065F46'   # green text for done status
    COLOR_OVERDUE    = '991B1B'   # red text for overdue

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0'),
    )
    thick_bottom = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='medium', color=COLOR_ACCENT),
    )

    # ── Header row ──
    hfont  = Font(bold=True, color='FFFFFF', size=11, name='Calibri')
    hfill  = PatternFill(start_color=COLOR_ACCENT, end_color=COLOR_ACCENT, fill_type='solid')
    halign = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap   = Alignment(wrap_text=True, vertical='top')
    left   = Alignment(wrap_text=True, vertical='top', horizontal='left')

    headers = ['Дата', 'Проект', 'Задача / описание', 'Статус', 'Инициатор', 'Часы', 'Обоснование']
    widths  = [13, 26, 52, 18, 24, 9, 42]

    ws.row_dimensions[1].height = 26
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font   = hfont
        c.fill   = hfill
        c.alignment = halign
        c.border = thick_bottom
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Data rows ──
    status_map   = dict(Task.STATUS_CHOICES)
    total_hours  = Decimal('0')
    odd_fill     = PatternFill(start_color=COLOR_ROW_ODD,  end_color=COLOR_ROW_ODD,  fill_type='solid')
    even_fill    = PatternFill(start_color=COLOR_ROW_EVEN, end_color=COLOR_ROW_EVEN, fill_type='solid')

    from datetime import date as _date
    today = _date.today()

    for ri, task in enumerate(tasks_list, 2):
        h = task.hours or None
        if h:
            total_hours += h

        row_data = [
            task.date.strftime('%d.%m.%Y'),
            task.project.name,
            task.task,
            status_map.get(task.status, task.status),
            task.initiator or '—',
            float(h) if h else '—',
            task.basis or '—',
        ]
        fill = even_fill if ri % 2 == 0 else odd_fill
        ws.row_dimensions[ri].height = 36

        for ci, val in enumerate(row_data, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill   = fill
            c.border = thin_border
            c.alignment = left if ci in (3, 7) else Alignment(vertical='top', horizontal='center' if ci in (1,4,6) else 'left')

            # Color status cell
            if ci == 4:
                if task.status == Task.STATUS_DONE:
                    c.font = Font(color=COLOR_DONE, name='Calibri')
                elif task.due_date and task.due_date < today and task.status != Task.STATUS_DONE:
                    c.font = Font(color=COLOR_OVERDUE, bold=True, name='Calibri')

    # ── Summary row ──
    sr = len(tasks_list) + 2
    ws.row_dimensions[sr].height = 22
    total_fill = PatternFill(start_color=COLOR_TOTAL_BG, end_color=COLOR_TOTAL_BG, fill_type='solid')
    summary_border = Border(
        top=Side(style='medium', color=COLOR_ACCENT),
        bottom=Side(style='thin', color='E2E8F0'),
    )
    for ci in range(1, 8):
        c = ws.cell(row=sr, column=ci)
        c.fill   = total_fill
        c.border = summary_border
    ws.cell(row=sr, column=1, value='Итого:').font  = Font(bold=True, color=COLOR_ACCENT, name='Calibri')
    ws.cell(row=sr, column=1).alignment = Alignment(horizontal='right', vertical='center')
    total_cell = ws.cell(row=sr, column=6, value=float(total_hours))
    total_cell.font      = Font(bold=True, color=COLOR_ACCENT, name='Calibri')
    total_cell.alignment = Alignment(horizontal='center', vertical='center')
    count_cell = ws.cell(row=sr, column=3, value=f'Задач: {len(tasks_list)}')
    count_cell.font      = Font(color='64748B', name='Calibri')
    count_cell.alignment = Alignment(horizontal='left', vertical='center')

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:G{len(tasks_list) + 1}'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    period = f'{date_from}__{date_to}' if (date_from or date_to) else 'all'
    response['Content-Disposition'] = f'attachment; filename="report_{period}.xlsx"'
    wb.save(response)
    return response