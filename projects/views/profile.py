from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from ..models import UserProfile


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')

        if action == 'password':
            current = request.POST.get('current_password', '')
            new_pw  = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')
            if not request.user.check_password(current):
                messages.error(request, 'Текущий пароль неверный')
            elif len(new_pw) < 8:
                messages.error(request, 'Новый пароль должен быть не менее 8 символов')
            elif new_pw != confirm:
                messages.error(request, 'Пароли не совпадают')
            else:
                request.user.set_password(new_pw)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Пароль успешно изменён')
            return redirect('profile')

        # action == 'profile'
        profile_obj.last_name   = request.POST.get('last_name', '').strip()
        profile_obj.first_name  = request.POST.get('first_name', '').strip()
        profile_obj.middle_name = request.POST.get('middle_name', '').strip()
        profile_obj.position    = request.POST.get('position', '').strip()
        profile_obj.department  = request.POST.get('department', '').strip()
        profile_obj.save()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save(update_fields=['email'])
        messages.success(request, 'Профиль обновлён')
        return redirect('profile')

    return render(request, 'projects/profile.html', {'profile': profile_obj})
