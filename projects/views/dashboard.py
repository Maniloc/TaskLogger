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


# ── Dashboard ─────────────────────────────────────────────

@login_required
def index(request):
    projects = Project.objects.filter(user=request.user).annotate(
        task_count_ann=Count('tasks'),
        hours_total=Sum('tasks__hours'),
    )
    today = date.today()
    month_start = today.replace(day=1)
    from django.db.models import Case, When, Value, IntegerField
    active_tasks = (
        Task.objects
        .filter(
            project__user=request.user,
            status__in=[Task.STATUS_TODO, Task.STATUS_IN_PROGRESS, Task.STATUS_DEFERRED]
        )
        .select_related('project')
        .annotate(
            urgency_order=Case(
                When(due_date__lt=today, then=Value(0)),
                When(due_date=today, then=Value(1)),
                When(due_date__lte=today + timedelta(days=3), then=Value(2)),
                When(due_date__lte=today + timedelta(days=7), then=Value(3)),
                When(due_date__isnull=False, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .order_by('urgency_order', 'due_date', '-date')[:10]
    )
    recent_tasks = active_tasks

    agg = Task.objects.filter(
        project__user=request.user,
        date__gte=month_start,
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    last_date = (
        Task.objects.filter(project__user=request.user)
        .order_by('-date').values_list('date', flat=True).first()
    )
    gap_days = None
    if last_date:
        delta = (today - last_date).days
        if delta >= 2:
            gap_days = delta

    # ── Dashboard charts ──
    fourteen_days_ago = today - timedelta(days=13)
    daily_qs = (
        Task.objects
        .filter(project__user=request.user, date__gte=fourteen_days_ago)
        .values('date')
        .annotate(count=Count('id'), hours=Sum('hours'))
    )
    daily_map = {str(row['date']): row for row in daily_qs}
    chart_days, chart_counts, chart_hours = [], [], []
    for i in range(14):
        d = fourteen_days_ago + timedelta(days=i)
        k = d.strftime('%Y-%m-%d')
        chart_days.append(d.strftime('%d.%m'))
        row = daily_map.get(k, {})
        chart_counts.append(row.get('count', 0))
        chart_hours.append(float(row.get('hours') or 0))

    # Project distribution by hours this month
    proj_dist = list(
        projects.filter(hours_total__gt=0).order_by('-hours_total')[:6]
    )
    proj_dist_labels = _jdumps([p.name for p in proj_dist])
    proj_dist_hours  = _jdumps([float(p.hours_total or 0) for p in proj_dist])

    done_recent = (
        Task.objects
        .filter(project__user=request.user, status=Task.STATUS_DONE, date__gte=month_start)
        .select_related('project')
        .order_by('-date')[:20]
    )

    # Group active tasks by urgency for sidebar
    active_grouped = {'overdue': [], 'today': [], 'soon': [], 'upcoming': [], 'other': []}
    for t in active_tasks:
        u = t.urgency
        if u in active_grouped:
            active_grouped[u].append(t)
        else:
            active_grouped['other'].append(t)
    active_total = sum(len(v) for v in active_grouped.values())

    return render(request, 'projects/index.html', {
        'projects': projects,
        'recent_tasks': recent_tasks,
        'done_recent': done_recent,
        'active_grouped': active_grouped,
        'active_total': active_total,
        'tasks_count': agg['count'] or 0,
        'tasks_hours': agg['hours'] or Decimal('0'),
        'today': today,
        'gap_days': gap_days,
        'chart_days':        _jdumps(chart_days),
        'chart_counts':      _jdumps(chart_counts),
        'chart_hours':       _jdumps(chart_hours),
        'proj_dist_labels':  proj_dist_labels,
        'proj_dist_hours':   proj_dist_hours,
    })