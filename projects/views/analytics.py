import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from datetime import date, timedelta
from decimal import Decimal
from ..models import Project, Task
from .utils import _jdumps, _month_key, _day_key


# ── Analytics ─────────────────────────────────────────────


@login_required
def analytics(request):
    today = date.today()

    # ── Date range from GET params ──
    date_from_str = request.GET.get('date_from', '')
    date_to_str   = request.GET.get('date_to', '')

    try:
        if date_from_str:
            from datetime import datetime as _dt
            range_start = _dt.strptime(date_from_str, '%Y-%m-%d').date()
        else:
            range_start = (today.replace(day=1) - timedelta(days=335)).replace(day=1)
    except ValueError:
        range_start = (today.replace(day=1) - timedelta(days=335)).replace(day=1)

    try:
        if date_to_str:
            from datetime import datetime as _dt
            range_end = _dt.strptime(date_to_str, '%Y-%m-%d').date()
        else:
            range_end = today
    except ValueError:
        range_end = today

    # ── 1. Monthly dynamics ──
    twelve_months_ago = range_start

    monthly_qs = (
        Task.objects
        .filter(project__user=request.user, date__gte=range_start, date__lte=range_end)
        .values('date__year', 'date__month')
        .annotate(count=Count('id'), hours=Sum('hours'))
        .order_by('date__year', 'date__month')
    )

    # Build full 12-month series (fill gaps with 0)
    months_map = {}
    for row in monthly_qs:
        key = f"{row['date__year']:04d}-{row['date__month']:02d}"
        months_map[key] = {
            'count': row['count'],
            'hours': float(row['hours'] or 0),
        }

    monthly_labels = []
    monthly_counts = []
    monthly_hours = []
    cursor = twelve_months_ago
    while cursor <= range_end.replace(day=1):
        key = cursor.strftime('%Y-%m')
        label = cursor.strftime('%b %Y')
        monthly_labels.append(label)
        monthly_counts.append(months_map.get(key, {}).get('count', 0))
        monthly_hours.append(round(months_map.get(key, {}).get('hours', 0), 1))
        # next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    # ── 2. Daily activity ──
    thirty_days_ago = range_start
    range_days = max(1, (range_end - range_start).days + 1)

    daily_qs = (
        Task.objects
        .filter(project__user=request.user, date__gte=range_start, date__lte=range_end)
        .values('date')
        .annotate(count=Count('id'), hours=Sum('hours'))
        .order_by('date')
    )

    daily_map = {}
    for row in daily_qs:
        key = str(row['date'])
        daily_map[key] = {
            'count': row['count'],
            'hours': float(row['hours'] or 0),
        }

    daily_labels = []
    daily_counts = []
    daily_hours = []
    for i in range(range_days):
        d = thirty_days_ago + timedelta(days=i)
        key = d.strftime('%Y-%m-%d')
        daily_labels.append(d.strftime('%d.%m'))
        daily_counts.append(daily_map.get(key, {}).get('count', 0))
        daily_hours.append(round(daily_map.get(key, {}).get('hours', 0), 1))

    # ── 3. Status breakdown (all time) ──
    status_qs = (
        Task.objects
        .filter(project__user=request.user)
        .values('status')
        .annotate(count=Count('id'))
    )
    status_map_labels = dict(Task.STATUS_CHOICES)
    status_labels = []
    status_counts = []
    for row in status_qs:
        status_labels.append(status_map_labels.get(row['status'], row['status']))
        status_counts.append(row['count'])

    # ── 4. Top projects by hours ──
    top_projects_qs = (
        Project.objects
        .filter(user=request.user)
        .annotate(hours_total=Sum('tasks__hours'), task_count=Count('tasks'))
        .filter(hours_total__gt=0)
        .order_by('-hours_total')[:8]
    )
    proj_labels = [p.name for p in top_projects_qs]
    proj_hours = [float(p.hours_total or 0) for p in top_projects_qs]

    # ── Summary stats ──
    total_all = Task.objects.filter(project__user=request.user).aggregate(
        count=Count('id'), hours=Sum('hours')
    )
    this_month = Task.objects.filter(
        project__user=request.user,
        date__gte=today.replace(day=1)
    ).aggregate(count=Count('id'), hours=Sum('hours'))
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = today.replace(day=1) - timedelta(days=1)
    last_month = Task.objects.filter(
        project__user=request.user,
        date__gte=last_month_start,
        date__lte=last_month_end,
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    # ── 5. Overdue tasks by month (due_date in past, not done) ──
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
    overdue_monthly_map = {}
    for row in overdue_monthly_qs:
        key = f"{row['due_date__year']:04d}-{row['due_date__month']:02d}"
        overdue_monthly_map[key] = row['count']

    monthly_overdue = []
    cursor2 = twelve_months_ago
    while cursor2 <= range_end.replace(day=1):
        key = cursor2.strftime('%Y-%m')
        monthly_overdue.append(overdue_monthly_map.get(key, 0))
        if cursor2.month == 12:
            cursor2 = cursor2.replace(year=cursor2.year + 1, month=1)
        else:
            cursor2 = cursor2.replace(month=cursor2.month + 1)

    # ── 6. Overdue tasks by day (last 30 days) ──
    overdue_daily_qs = (
        Task.objects
        .filter(
            project__user=request.user,
            due_date__isnull=False,
            due_date__gte=range_start,
            due_date__lte=range_end,
            due_date__lt=today,
        )
        .exclude(status=Task.STATUS_DONE)
        .values('due_date')
        .annotate(count=Count('id'))
        .order_by('due_date')
    )
    overdue_daily_map = {str(r['due_date']): r['count'] for r in overdue_daily_qs}
    daily_overdue = []
    for i in range(range_days):
        d = thirty_days_ago + timedelta(days=i)
        daily_overdue.append(overdue_daily_map.get(d.strftime('%Y-%m-%d'), 0))

    # ── 7. Overdue summary ──
    overdue_total = Task.objects.filter(
        project__user=request.user,
        due_date__lt=today,
        due_date__isnull=False,
    ).exclude(status=Task.STATUS_DONE).count()

    overdue_by_project = (
        Project.objects
        .filter(user=request.user)
        .annotate(
            overdue_count=Count(
                'tasks',
                filter=__import__('django.db.models', fromlist=['Q']).Q(
                    tasks__due_date__lt=today,
                    tasks__due_date__isnull=False,
                ) & ~__import__('django.db.models', fromlist=['Q']).Q(tasks__status=Task.STATUS_DONE)
            )
        )
        .filter(overdue_count__gt=0)
        .order_by('-overdue_count')[:6]
    )
    overdue_proj_labels = _jdumps([p.name for p in overdue_by_project])
    overdue_proj_counts = _jdumps([p.overdue_count for p in overdue_by_project])

    return render(request, 'projects/analytics.html', {
        'monthly_labels':     _jdumps(monthly_labels),
        'monthly_counts':     _jdumps(monthly_counts),
        'monthly_hours':      _jdumps(monthly_hours),
        'monthly_overdue':    _jdumps(monthly_overdue),
        'daily_labels':       _jdumps(daily_labels),
        'daily_counts':       _jdumps(daily_counts),
        'daily_hours':        _jdumps(daily_hours),
        'daily_overdue':      _jdumps(daily_overdue),
        'status_labels':      _jdumps(status_labels),
        'status_counts':      _jdumps(status_counts),
        'proj_labels':        _jdumps(proj_labels),
        'proj_hours':         _jdumps(proj_hours),
        'overdue_total':      overdue_total,
        'overdue_proj_labels': overdue_proj_labels,
        'overdue_proj_counts': overdue_proj_counts,
        'total_all':          total_all,
        'this_month':         this_month,
        'last_month':         last_month,
        'today':              today,
    })