"""
Project membership views:
  - manage members (add/change role/remove) — owner only
  - participant dashboard (/my-tasks/)
  - participant project detail (shared projects)
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
from ..models import Project, Task, ProjectMember, Conversation, Message


def _get_membership(user, project):
    """Return ProjectMember or None."""
    return ProjectMember.objects.filter(project=project, user=user).first()


def _require_member(user, project, min_role=None):
    """Return membership or None if no access."""
    m = _get_membership(user, project)
    if not m:
        return None
    if min_role == 'owner' and m.role != ProjectMember.ROLE_OWNER:
        return None
    return m


def _notify_assignment(assigner, assignee, task):
    """Send chat notification when task is assigned."""
    if assigner == assignee:
        return
    try:
        conv = (
            Conversation.objects
            .filter(participants=assigner, is_group=False)
            .filter(participants=assignee)
            .first()
        )
        if not conv:
            conv = Conversation.objects.create(is_group=False, created_by=assigner)
            conv.participants.add(assigner, assignee)
        proj_name = task.project.name
        text = (
            f'📌 Вам назначена задача в проекте «{proj_name}»:\n'
            f'{task.task[:200]}'
        )
        Message.objects.create(conversation=conv, sender=assigner, text=text)
    except Exception:
        pass


# ── Member management ──────────────────────────────────────

@login_required
def project_members(request, pk):
    """Show and manage project members (owner only)."""
    project = get_object_or_404(Project, pk=pk)
    membership = _get_membership(request.user, project)

    # Owner of the project model OR project member with owner role
    is_owner = (project.user == request.user) or (
        membership and membership.role == ProjectMember.ROLE_OWNER
    )
    if not is_owner:
        messages.error(request, 'Только владелец может управлять участниками')
        return redirect('project_detail', pk=pk)

    members = ProjectMember.objects.filter(project=project).select_related('user', 'user__profile')
    member_ids = set(m.user_id for m in members) | {project.user_id}
    available_users = User.objects.exclude(pk__in=member_ids).order_by('username')

    return render(request, 'projects/project_members.html', {
        'project': project,
        'members': members,
        'available_users': available_users,
        'role_choices': ProjectMember.ROLE_CHOICES,
        'is_owner': is_owner,
    })


@login_required
@require_POST
def member_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.user != request.user and not _require_member(request.user, project, 'owner'):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    user_id = request.POST.get('user_id')
    role    = request.POST.get('role', ProjectMember.ROLE_EXECUTOR)
    if role not in dict(ProjectMember.ROLE_CHOICES):
        role = ProjectMember.ROLE_EXECUTOR
    user = get_object_or_404(User, pk=user_id)
    obj, created = ProjectMember.objects.get_or_create(
        project=project, user=user,
        defaults={'role': role}
    )
    if not created:
        obj.role = role
        obj.save(update_fields=['role'])
    messages.success(request, f'Пользователь {user.username} добавлен как «{obj.get_role_display()}»')
    return redirect('project_members', pk=pk)


@login_required
@require_POST
def member_remove(request, pk, user_id):
    project = get_object_or_404(Project, pk=pk)
    if project.user != request.user and not _require_member(request.user, project, 'owner'):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    if int(user_id) == project.user_id:
        messages.error(request, 'Нельзя удалить владельца проекта')
        return redirect('project_members', pk=pk)
    ProjectMember.objects.filter(project=project, user_id=user_id).delete()
    messages.success(request, 'Участник удалён')
    return redirect('project_members', pk=pk)


@login_required
@require_POST
def member_role(request, pk, user_id):
    project = get_object_or_404(Project, pk=pk)
    if project.user != request.user and not _require_member(request.user, project, 'owner'):
        return JsonResponse({'error': 'Нет прав'}, status=403)
    role = request.POST.get('role', ProjectMember.ROLE_EXECUTOR)
    if role not in dict(ProjectMember.ROLE_CHOICES):
        return JsonResponse({'error': 'Неверная роль'}, status=400)
    m = get_object_or_404(ProjectMember, project=project, user_id=user_id)
    m.role = role
    m.save(update_fields=['role'])
    return JsonResponse({'role': m.role, 'display': m.get_role_display()})


# ── Participant dashboard ──────────────────────────────────

@login_required
def my_tasks(request):
    """Dashboard for project participants — shows tasks assigned/created in shared projects."""
    today = date.today()
    month_start = today.replace(day=1)

    # Projects where user is a member (not owner)
    memberships = ProjectMember.objects.filter(user=request.user).select_related('project')
    shared_projects = [m.project for m in memberships]
    shared_pids = [p.pk for p in shared_projects]

    # Own projects (user is owner)
    own_projects = list(Project.objects.filter(user=request.user).annotate(
        task_count_ann=Count('tasks'), hours_total=Sum('tasks__hours')
    ))

    # Tasks in shared projects visible to this user
    if memberships:
        # Executors and observers see all tasks in shared projects
        shared_tasks = (
            Task.objects
            .filter(project_id__in=shared_pids)
            .select_related('project', 'assigned_to', 'assigned_to__profile')
            .order_by('-date')[:20]
        )
    else:
        shared_tasks = Task.objects.none()

    # My assigned tasks across ALL projects
    assigned_tasks = (
        Task.objects
        .filter(assigned_to=request.user)
        .exclude(status=Task.STATUS_DONE)
        .select_related('project')
        .annotate(
            urgency_order=__import__('django.db.models', fromlist=['Case']).Case(
                __import__('django.db.models', fromlist=['When']).When(due_date__lt=today, then=0),
                __import__('django.db.models', fromlist=['When']).When(due_date=today, then=1),
                __import__('django.db.models', fromlist=['When']).When(
                    due_date__lte=today+timedelta(days=3), then=2),
                default=3,
                output_field=__import__('django.db.models', fromlist=['IntegerField']).IntegerField(),
            )
        )
        .order_by('urgency_order', 'due_date')[:15]
    )

    # Stats for this month
    my_month = (
        Task.objects
        .filter(
            Q(project__user=request.user) | Q(project_id__in=shared_pids),
            date__gte=month_start,
            assigned_to=request.user,
        )
        .aggregate(count=Count('id'), hours=Sum('hours'))
    )

    return render(request, 'projects/my_tasks.html', {
        'memberships':    memberships,
        'shared_projects': shared_projects,
        'own_projects':   own_projects,
        'shared_tasks':   shared_tasks,
        'assigned_tasks': assigned_tasks,
        'my_month':       my_month,
        'today':          today,
    })


# ── Shared project detail ──────────────────────────────────

@login_required
def shared_project_detail(request, pk):
    """Project detail for members (non-owners)."""
    project = get_object_or_404(Project, pk=pk)
    membership = _get_membership(request.user, project)

    # Allow owner too
    if project.user == request.user:
        return redirect('project_detail', pk=pk)
    if not membership:
        messages.error(request, 'У вас нет доступа к этому проекту')
        return redirect('my_tasks')

    can_add    = membership.can_add_tasks
    can_edit   = membership.role == ProjectMember.ROLE_OWNER

    # Members for assignment dropdown
    members_qs = ProjectMember.objects.filter(project=project).select_related('user', 'user__profile')
    member_users = [m.user for m in members_qs] + [project.user]

    # Tasks — all visible
    tasks = Task.objects.filter(project=project).select_related(
        'assigned_to', 'assigned_to__profile'
    ).order_by('-date')

    # Handle POST: add task
    if request.method == 'POST' and can_add:
        from .utils import _parse_hours
        task_text = request.POST.get('task', '').strip()
        if task_text:
            try:
                hours = _parse_hours(request.POST.get('hours', ''))
            except ValueError:
                hours = None
            assigned_id = request.POST.get('assigned_to', '')
            assigned_user = None
            if assigned_id:
                try:
                    assigned_user = User.objects.get(pk=int(assigned_id))
                except (User.DoesNotExist, ValueError):
                    pass
            t = Task.objects.create(
                project=project,
                date=request.POST.get('date') or date.today(),
                task=task_text,
                status=request.POST.get('status', Task.STATUS_IN_PROGRESS),
                initiator=request.POST.get('initiator', '').strip(),
                hours=hours,
                start_date=request.POST.get('start_date') or None,
                due_date=request.POST.get('due_date') or None,
                basis=request.POST.get('basis', '').strip(),
                assigned_to=assigned_user,
            )
            # Notify assignee
            if assigned_user and assigned_user != request.user:
                _notify_assignment(request.user, assigned_user, t)
            messages.success(request, 'Задача добавлена')
        return redirect('shared_project_detail', pk=pk)

    return render(request, 'projects/shared_project_detail.html', {
        'project':      project,
        'membership':   membership,
        'can_add':      can_add,
        'can_edit':     can_edit,
        'member_users': member_users,
        'tasks':        tasks,
        'status_choices': Task.STATUS_CHOICES,
        'members':      members_qs,
    })
