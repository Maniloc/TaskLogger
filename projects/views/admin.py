from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from datetime import date
from decimal import Decimal
from ..models import Project, Task
from .utils import superuser_required


# ── Admin Panel ───────────────────────────────────────────



@superuser_required
def admin_panel(request):
    users = User.objects.exclude(pk=request.user.pk).annotate(
        project_count=Count('projects'),
        task_count=Count('projects__tasks'),
        hours_total=Sum('projects__tasks__hours'),
    ).order_by('username')

    # global stats
    all_tasks = Task.objects.select_related('project', 'project__user')
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        all_tasks = all_tasks.filter(
            Q(task__icontains=search) |
            Q(project__name__icontains=search) |
            Q(project__user__username__icontains=search)
        )
    if status_filter:
        all_tasks = all_tasks.filter(status=status_filter)
    if user_filter:
        all_tasks = all_tasks.filter(project__user_id=user_filter)
    if date_from:
        all_tasks = all_tasks.filter(date__gte=date_from)
    if date_to:
        all_tasks = all_tasks.filter(date__lte=date_to)

    all_tasks = all_tasks.order_by('-date', '-created_at')

    total_hours = all_tasks.aggregate(t=Sum('hours'))['t'] or Decimal('0')

    paginator = Paginator(all_tasks, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    all_users = User.objects.exclude(is_superuser=True).order_by('username')

    return render(request, 'projects/admin_panel.html', {
        'users': users,
        'page_obj': page_obj,
        'tasks': page_obj,
        'total_hours': total_hours,
        'total_count': all_tasks.count(),
        'search': search,
        'status_filter': status_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Task.STATUS_CHOICES,
        'all_users': all_users,
    })


@superuser_required
def admin_user_detail(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    projects = Project.objects.filter(user=target_user).annotate(
        task_count_ann=Count('tasks'),
        hours_total=Sum('tasks__hours'),
    )

    today = date.today()
    month_start = today.replace(day=1)
    tasks_month = Task.objects.filter(
        project__user=target_user, date__gte=month_start
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    recent_tasks = Task.objects.filter(
        project__user=target_user
    ).select_related('project').order_by('-date')[:10]

    total = Task.objects.filter(project__user=target_user).aggregate(
        count=Count('id'), hours=Sum('hours')
    )

    return render(request, 'projects/admin_user_detail.html', {
        'target_user': target_user,
        'projects': projects,
        'recent_tasks': recent_tasks,
        'tasks_month': tasks_month,
        'total': total,
    })