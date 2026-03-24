import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from datetime import date, timedelta, datetime
from decimal import Decimal
from ..models import Project, Task
from .utils import _jdumps


# ── Analytics ─────────────────────────────────────────────


@login_required
def analytics(request):
    today = date.today()

    # ── Parse date range ──
    date_from_str = request.GET.get('date_from', '')
    date_to_str   = request.GET.get('date_to', '')

    try:
        range_start = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    except ValueError:
        range_start = None

    try:
        range_end = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None
    except ValueError:
        range_end = None

    # Defaults: last 12 months
    default_start = (today.replace(day=1) - timedelta(days=335)).replace(day=1)
    default_end   = today

    range_start = range_start or default_start
    range_end   = range_end   or default_end

    # Clamp: end >= start
    if range_end < range_start:
        range_end = range_start

    # Base queryset filtered by range — used EVERYWHERE
    base_qs = Task.objects.filter(
        project__user=request.user,
        date__gte=range_start,
        date__lte=range_end,
    )

    # ── Summary stat cards (respect range) ──
    total_range = base_qs.aggregate(count=Count('id'), hours=Sum('hours'))

    # Previous period for comparison (same length before range_start)
    period_days = max(1, (range_end - range_start).days + 1)
    prev_start  = range_start - timedelta(days=period_days)
    prev_end    = range_start - timedelta(days=1)
    prev_qs = Task.objects.filter(
        project__user=request.user,
        date__gte=prev_start,
        date__lte=prev_end,
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    # Overdue in range
    overdue_total = Task.objects.filter(
        project__user=request.user,
        due_date__lt=today,
        due_date__isnull=False,
        due_date__gte=range_start,
        due_date__lte=range_end,
    ).exclude(status=Task.STATUS_DONE).count()

    # ── 1. Monthly dynamics ──
    monthly_qs = (
        base_qs
        .values('date__year', 'date__month')
        .annotate(count=Count('id'), hours=Sum('hours'))
        .order_by('date__year', 'date__month')
    )
    months_map = {}
    for row in monthly_qs:
        key = f"{row['date__year']:04d}-{row['date__month']:02d}"
        months_map[key] = {'count': row['count'], 'hours': float(row['hours'] or 0)}

    monthly_labels, monthly_counts, monthly_hours = [], [], []
    cursor = range_start.replace(day=1)
    while cursor <= range_end.replace(day=1):
        key = cursor.strftime('%Y-%m')
        monthly_labels.append(cursor.strftime('%b %Y'))
        monthly_counts.append(months_map.get(key, {}).get('count', 0))
        monthly_hours.append(round(months_map.get(key, {}).get('hours', 0), 1))
        cursor = cursor.replace(month=cursor.month % 12 + 1, year=cursor.year + (1 if cursor.month == 12 else 0))

    # ── 2. Daily activity ──
    range_days = period_days
    # Cap daily chart at 90 days to avoid clutter
    daily_start = max(range_start, range_end - timedelta(days=89)) if range_days > 90 else range_start
    daily_range_days = (range_end - daily_start).days + 1

    daily_qs = (
        Task.objects.filter(
            project__user=request.user,
            date__gte=daily_start,
            date__lte=range_end,
        )
        .values('date')
        .annotate(count=Count('id'), hours=Sum('hours'))
        .order_by('date')
    )
    daily_map = {str(r['date']): {'count': r['count'], 'hours': float(r['hours'] or 0)} for r in daily_qs}

    daily_labels, daily_counts, daily_hours = [], [], []
    for i in range(daily_range_days):
        d = daily_start + timedelta(days=i)
        k = d.strftime('%Y-%m-%d')
        daily_labels.append(d.strftime('%d.%m'))
        daily_counts.append(daily_map.get(k, {}).get('count', 0))
        daily_hours.append(round(daily_map.get(k, {}).get('hours', 0), 1))

    # ── 3. Status breakdown (respect range) ──
    status_qs = (
        base_qs
        .values('status')
        .annotate(count=Count('id'))
    )
    status_map_labels = dict(Task.STATUS_CHOICES)
    status_labels, status_counts = [], []
    for row in status_qs:
        status_labels.append(status_map_labels.get(row['status'], row['status']))
        status_counts.append(row['count'])

    # ── 4. Top projects by hours (respect range) ──
    top_projects_qs = (
        Project.objects
        .filter(user=request.user)
        .annotate(
            hours_total=Sum('tasks__hours', filter=Q(tasks__date__gte=range_start, tasks__date__lte=range_end)),
            task_count=Count('tasks', filter=Q(tasks__date__gte=range_start, tasks__date__lte=range_end)),
        )
        .filter(hours_total__gt=0)
        .order_by('-hours_total')[:8]
    )
    proj_labels = [p.name for p in top_projects_qs]
    proj_hours  = [float(p.hours_total or 0) for p in top_projects_qs]

    # ── 5. Overdue by month ──
    overdue_monthly_qs = (
        Task.objects
        .filter(
            project__user=request.user,
            due_date__isnull=False,
            due_date__lt=today,
            due_date__gte=range_start,
            due_date__lte=range_end,
        )
        .exclude(status=Task.STATUS_DONE)
        .values('due_date__year', 'due_date__month')
        .annotate(count=Count('id'))
        .order_by('due_date__year', 'due_date__month')
    )
    overdue_monthly_map = {
        f"{r['due_date__year']:04d}-{r['due_date__month']:02d}": r['count']
        for r in overdue_monthly_qs
    }
    monthly_overdue = []
    cursor2 = range_start.replace(day=1)
    while cursor2 <= range_end.replace(day=1):
        monthly_overdue.append(overdue_monthly_map.get(cursor2.strftime('%Y-%m'), 0))
        cursor2 = cursor2.replace(month=cursor2.month % 12 + 1, year=cursor2.year + (1 if cursor2.month == 12 else 0))

    # ── 6. Overdue by day ──
    overdue_daily_qs = (
        Task.objects
        .filter(
            project__user=request.user,
            due_date__isnull=False,
            due_date__gte=daily_start,
            due_date__lte=range_end,
            due_date__lt=today,
        )
        .exclude(status=Task.STATUS_DONE)
        .values('due_date')
        .annotate(count=Count('id'))
        .order_by('due_date')
    )
    overdue_daily_map = {str(r['due_date']): r['count'] for r in overdue_daily_qs}
    daily_overdue = [
        overdue_daily_map.get((daily_start + timedelta(days=i)).strftime('%Y-%m-%d'), 0)
        for i in range(daily_range_days)
    ]

    # ── 7. Overdue by project ──
    overdue_by_project = (
        Project.objects
        .filter(user=request.user)
        .annotate(
            overdue_count=Count(
                'tasks',
                filter=Q(
                    tasks__due_date__lt=today,
                    tasks__due_date__isnull=False,
                    tasks__due_date__gte=range_start,
                    tasks__due_date__lte=range_end,
                ) & ~Q(tasks__status=Task.STATUS_DONE)
            )
        )
        .filter(overdue_count__gt=0)
        .order_by('-overdue_count')[:6]
    )

    return render(request, 'projects/analytics.html', {
        'monthly_labels':      _jdumps(monthly_labels),
        'monthly_counts':      _jdumps(monthly_counts),
        'monthly_hours':       _jdumps(monthly_hours),
        'monthly_overdue':     _jdumps(monthly_overdue),
        'daily_labels':        _jdumps(daily_labels),
        'daily_counts':        _jdumps(daily_counts),
        'daily_hours':         _jdumps(daily_hours),
        'daily_overdue':       _jdumps(daily_overdue),
        'status_labels':       _jdumps(status_labels),
        'status_counts':       _jdumps(status_counts),
        'proj_labels':         _jdumps(proj_labels),
        'proj_hours':          _jdumps(proj_hours),
        'overdue_total':       overdue_total,
        'overdue_proj_labels': _jdumps([p.name for p in overdue_by_project]),
        'overdue_proj_counts': _jdumps([p.overdue_count for p in overdue_by_project]),
        # Stats respect the selected range
        'total_range':         total_range,
        'prev_range':          prev_qs,
        'range_days':          range_days,
        'today':               today,
        'date_from':           range_start.strftime('%Y-%m-%d'),
        'date_to':             range_end.strftime('%Y-%m-%d'),
        'range_label':         f"{range_start.strftime('%d.%m.%Y')} — {range_end.strftime('%d.%m.%Y')}",
        'presets':             [('7д', 7), ('30д', 30), ('90д', 90), ('год', 365)],
    })
