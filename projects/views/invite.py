from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.http import JsonResponse
from ..models import InviteToken, UserProfile


@login_required
@require_POST
def invite_create(request):
    """Generate an invite link (superusers or any user depending on settings)."""
    days = int(request.POST.get('days', 7))
    days = max(1, min(days, 30))
    token = InviteToken.generate(request.user, days=days)
    invite_url = request.build_absolute_uri(f'/invite/{token.token}/')
    return JsonResponse({'url': invite_url, 'expires_days': days})


def invite_landing(request, token):
    """Public landing page for invite link."""
    invite = get_object_or_404(InviteToken, token=token)

    if not invite.is_valid():
        return render(request, 'projects/invite/expired.html')

    if request.user.is_authenticated:
        messages.info(request, 'Вы уже авторизованы.')
        return redirect('index')

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '').strip()
        password2  = request.POST.get('password2', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        middle_name= request.POST.get('middle_name', '').strip()
        position   = request.POST.get('position', '').strip()

        errors = []
        if not username:
            errors.append('Введите логин')
        elif User.objects.filter(username=username).exists():
            errors.append('Логин уже занят')
        if len(password) < 8:
            errors.append('Пароль должен быть не менее 8 символов')
        if password != password2:
            errors.append('Пароли не совпадают')

        if errors:
            return render(request, 'projects/invite/landing.html', {
                'invite': invite, 'errors': errors,
                'form': request.POST,
            })

        user = User.objects.create_user(username=username, password=password)
        profile = UserProfile.objects.get_or_create(user=user)[0]
        profile.first_name  = first_name
        profile.last_name   = last_name
        profile.middle_name = middle_name
        profile.position    = position
        profile.save()

        invite.used    = True
        invite.used_by = user
        invite.save(update_fields=['used', 'used_by'])

        from django.contrib.auth import login
        login(request, user)
        messages.success(request, f'Добро пожаловать, {first_name or username}!')
        return redirect('index')

    return render(request, 'projects/invite/landing.html', {
        'invite': invite, 'errors': [], 'form': {},
    })


@login_required
def invite_list(request):
    """Show created invites (admin panel use)."""
    invites = InviteToken.objects.filter(created_by=request.user).order_by('-created_at')[:20]
    return render(request, 'projects/invite/list.html', {'invites': invites})
