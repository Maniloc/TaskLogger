from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
from ..models import Project, Task, UserProfile, InviteToken
from .utils import superuser_required, _jdumps


@superuser_required
def admin_panel(request):
    today = date.today()
    month_start = today.replace(day=1)

    # ── Global stats ──
    total_users   = User.objects.count()
    active_users  = User.objects.filter(projects__tasks__date__gte=month_start).distinct().count()
    total_tasks   = Task.objects.count()
    total_hours   = Task.objects.aggregate(h=Sum('hours'))['h'] or Decimal('0')
    tasks_month   = Task.objects.filter(date__gte=month_start).count()
    hours_month   = Task.objects.filter(date__gte=month_start).aggregate(h=Sum('hours'))['h'] or Decimal('0')
    total_projects = Project.objects.count()
    overdue_count = Task.objects.filter(
        due_date__lt=today, due_date__isnull=False
    ).exclude(status=Task.STATUS_DONE).count()

    # ── User list with stats ──
    users = User.objects.annotate(
        project_count=Count('projects', distinct=True),
        task_count=Count('projects__tasks', distinct=True),
        hours_total=Sum('projects__tasks__hours'),
    ).order_by('-task_count')

    # ── Activity chart: tasks per day last 30 days ──
    thirty_ago = today - timedelta(days=29)
    day_qs = (
        Task.objects
        .filter(date__gte=thirty_ago)
        .values('date')
        .annotate(cnt=Count('id'))
        .order_by('date')
    )
    day_map = {str(r['date']): r['cnt'] for r in day_qs}
    chart_labels = []
    chart_data   = []
    for i in range(30):
        d = thirty_ago + timedelta(days=i)
        chart_labels.append(d.strftime('%d.%m'))
        chart_data.append(day_map.get(d.strftime('%Y-%m-%d'), 0))

    # ── Recent invites ──
    invites = InviteToken.objects.select_related('created_by', 'used_by').order_by('-created_at')[:10]

    return render(request, 'projects/admin_panel.html', {
        'users': users,
        'total_users':    total_users,
        'active_users':   active_users,
        'total_tasks':    total_tasks,
        'total_hours':    total_hours,
        'tasks_month':    tasks_month,
        'hours_month':    hours_month,
        'total_projects': total_projects,
        'overdue_count':  overdue_count,
        'chart_labels':   _jdumps(chart_labels),
        'chart_data':     _jdumps(chart_data),
        'invites':        invites,
        'today':          today,
        'status_choices': Task.STATUS_CHOICES,
    })


@superuser_required
def admin_user_detail(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    today = date.today()
    month_start = today.replace(day=1)

    projects = Project.objects.filter(user=target_user).annotate(
        task_count_ann=Count('tasks'),
        hours_total=Sum('tasks__hours'),
    ).order_by('-task_count_ann')

    tasks_month = Task.objects.filter(
        project__user=target_user, date__gte=month_start
    ).aggregate(count=Count('id'), hours=Sum('hours'))

    recent_tasks = Task.objects.filter(
        project__user=target_user
    ).select_related('project').order_by('-date')[:15]

    total = Task.objects.filter(project__user=target_user).aggregate(
        count=Count('id'), hours=Sum('hours')
    )

    overdue = Task.objects.filter(
        project__user=target_user,
        due_date__lt=today, due_date__isnull=False,
    ).exclude(status=Task.STATUS_DONE).count()

    return render(request, 'projects/admin_user_detail.html', {
        'target_user':  target_user,
        'projects':     projects,
        'recent_tasks': recent_tasks,
        'tasks_month':  tasks_month,
        'total':        total,
        'overdue':      overdue,
    })


@superuser_required
@require_POST
def admin_user_toggle(request, user_id):
    """Activate / deactivate user."""
    if user_id == request.user.pk:
        return JsonResponse({'error': 'Нельзя заблокировать себя'}, status=400)
    user = get_object_or_404(User, pk=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    return JsonResponse({'is_active': user.is_active, 'username': user.username})


@superuser_required
@require_POST
def admin_reset_password(request, user_id):
    """Set a new password for a user."""
    user = get_object_or_404(User, pk=user_id)
    new_pw = request.POST.get('password', '').strip()
    if len(new_pw) < 8:
        messages.error(request, 'Пароль должен быть не менее 8 символов')
        return redirect('admin_user_detail', user_id=user_id)
    user.set_password(new_pw)
    user.save()
    messages.success(request, f'Пароль пользователя {user.username} изменён')
    return redirect('admin_user_detail', user_id=user_id)


@superuser_required
@require_POST
def admin_user_delete(request, user_id):
    """Delete user and all their data."""
    if user_id == request.user.pk:
        messages.error(request, 'Нельзя удалить себя')
        return redirect('admin_panel')
    user = get_object_or_404(User, pk=user_id)
    username = user.username
    user.delete()
    messages.success(request, f'Пользователь {username} удалён вместе со всеми данными')
    return redirect('admin_panel')


@superuser_required
def admin_tasks(request):
    """Full task list across all users with filters."""
    all_tasks = Task.objects.select_related('project', 'project__user').order_by('-date', '-created_at')

    search      = request.GET.get('search', '')
    status_f    = request.GET.get('status', '')
    user_f      = request.GET.get('user', '')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')

    if search:
        all_tasks = all_tasks.filter(
            Q(task__icontains=search) |
            Q(project__name__icontains=search) |
            Q(project__user__username__icontains=search)
        )
    if status_f:
        all_tasks = all_tasks.filter(status=status_f)
    if user_f:
        all_tasks = all_tasks.filter(project__user_id=user_f)
    if date_from:
        all_tasks = all_tasks.filter(date__gte=date_from)
    if date_to:
        all_tasks = all_tasks.filter(date__lte=date_to)

    total_hours = all_tasks.aggregate(t=Sum('hours'))['t'] or Decimal('0')
    paginator   = Paginator(all_tasks, 30)
    page_obj    = paginator.get_page(request.GET.get('page'))
    all_users   = User.objects.order_by('username')

    return render(request, 'projects/admin_tasks.html', {
        'page_obj':       page_obj,
        'tasks':          page_obj,
        'total_hours':    total_hours,
        'total_count':    all_tasks.count(),
        'search':         search,
        'status_filter':  status_f,
        'user_filter':    user_f,
        'date_from':      date_from,
        'date_to':        date_to,
        'status_choices': Task.STATUS_CHOICES,
        'all_users':      all_users,
    })
