import json
import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Max
from django.utils import timezone
from ..models import Conversation, Message, ConversationSettings

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {
    'image':    ['image/jpeg','image/png','image/gif','image/webp'],
    'document': ['application/pdf','application/msword',
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                 'application/vnd.ms-excel',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 'text/plain','text/csv'],
    'archive':  ['application/zip','application/x-rar-compressed','application/x-7z-compressed'],
}
ALL_ALLOWED = sum(ALLOWED_TYPES.values(), [])


def _get_file_type(mime):
    for ftype, mimes in ALLOWED_TYPES.items():
        if mime in mimes:
            return ftype
    return 'file'


def _msg_to_dict(msg, current_user):
    # Avatar data for JS rendering
    try:
        prof = msg.sender.profile
        av = {'type': 'img', 'url': prof.avatar.url} if prof.avatar else {
            'type': 'initials',
            'text': prof.initials or msg.sender.username[:2].upper(),
            'color': prof.avatar_color or '',
        }
    except Exception:
        av = {'type': 'initials', 'text': msg.sender.username[:1].upper(), 'color': ''}

    d = {
        'id': msg.pk,
        'text': msg.text,
        'sender': msg.sender.username,
        'sender_id': msg.sender.pk,
        'sender_display': _display_name(msg.sender),
        'created_at': msg.created_at.strftime('%H:%M'),
        'date': msg.created_at.strftime('%d.%m.%Y'),
        'mine': msg.sender_id == current_user.pk,
        'avatar': av,
    }
    if msg.file:
        d['file'] = {
            'url': msg.file.url,
            'name': msg.file_name or os.path.basename(msg.file.name),
            'size': msg.file_size or 0,
            'type': msg.file_type or 'file',
        }
    return d


def _display_name(user):
    try:
        p = user.profile
        return p.display_name or user.username
    except Exception:
        return user.username


def _avatar_html(user, size=36):
    """Return context dict for avatar rendering."""
    try:
        p = user.profile
        if p.avatar:
            return {'type': 'img', 'url': p.avatar.url}
        return {'type': 'initials', 'initials': p.initials or user.username[:2].upper(),
                'color': p.avatar_color or ''}
    except Exception:
        return {'type': 'initials', 'initials': user.username[:2].upper(), 'color': ''}


def _update_online(user):
    try:
        user.profile.last_seen = timezone.now()
        user.profile.save(update_fields=['last_seen'])
    except Exception:
        pass


def _get_mute(user, conv):
    s = ConversationSettings.objects.filter(user=user, conversation=conv).first()
    return s.is_muted if s else False


def _sidebar_data(request, active_conv_id=None):
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related('participants')
        .annotate(last_msg_time=Max('messages__created_at'))
        .order_by('-last_msg_time')
    )
    convs_data = []
    for c in conversations:
        other = c.other_participant(request.user)
        last = c.last_message()
        unread = c.unread_count(request.user) if c.pk != active_conv_id else 0
        muted = _get_mute(request.user, c)
        convs_data.append({
            'conv': c,
            'other': other,
            'last': last,
            'unread': unread,
            'muted': muted,
            'title': c.display_title(request.user),
        })
    return convs_data


@login_required
def chat_list(request):
    _update_online(request.user)
    convs_data = _sidebar_data(request)
    all_users = User.objects.exclude(pk=request.user.pk).order_by('username')
    total_unread = sum(c['unread'] for c in convs_data)
    return render(request, 'projects/chat/list.html', {
        'convs_data': convs_data,
        'all_users': all_users,
        'total_unread': total_unread,
    })


@login_required
def chat_open(request, user_id):
    _update_online(request.user)
    other = get_object_or_404(User, pk=user_id)
    if other == request.user:
        return redirect('chat_list')
    conv = (
        Conversation.objects
        .filter(participants=request.user, is_group=False)
        .filter(participants=other)
        .first()
    )
    if not conv:
        conv = Conversation.objects.create(is_group=False, created_by=request.user)
        conv.participants.add(request.user, other)
    return redirect('chat_room', conv_id=conv.pk)


@login_required
@require_POST
def chat_create_group(request):
    """Create a group conversation."""
    _update_online(request.user)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    title = data.get('title', '').strip() or 'Беседа'
    user_ids = data.get('user_ids', [])
    if not user_ids:
        return JsonResponse({'error': 'Выберите участников'}, status=400)

    members = list(User.objects.filter(pk__in=user_ids))
    if not members:
        return JsonResponse({'error': 'Пользователи не найдены'}, status=400)

    conv = Conversation.objects.create(
        title=title, is_group=True, created_by=request.user
    )
    conv.participants.add(request.user, *members)
    return JsonResponse({'conv_id': conv.pk})


@login_required
def chat_room(request, conv_id):
    _update_online(request.user)
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    other = conv.other_participant(request.user)
    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    messages_qs = conv.messages.select_related('sender', 'sender__profile').order_by('created_at')
    convs_data = _sidebar_data(request, active_conv_id=conv.pk)
    all_users = User.objects.exclude(pk=request.user.pk).order_by('username')
    total_unread = sum(c['unread'] for c in convs_data)
    is_muted = _get_mute(request.user, conv)
    # Group participants (excluding self)
    group_members = list(conv.participants.exclude(pk=request.user.pk).select_related('profile')) if conv.is_group else []

    return render(request, 'projects/chat/room.html', {
        'conv': conv,
        'other': other,
        'messages_qs': messages_qs,
        'convs_data': convs_data,
        'all_users': all_users,
        'total_unread': total_unread,
        'is_muted': is_muted,
        'group_members': group_members,
    })


@login_required
@require_POST
def chat_send(request, conv_id):
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    _update_online(request.user)

    if request.content_type and 'multipart' in request.content_type:
        text = request.POST.get('text', '').strip()
        uploaded = request.FILES.get('file')
    else:
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}
        text = data.get('text', '').strip()
        uploaded = None

    if not text and not uploaded:
        return JsonResponse({'error': 'empty'}, status=400)

    msg = Message(conversation=conv, sender=request.user, text=text)

    if uploaded:
        mime = uploaded.content_type or mimetypes.guess_type(uploaded.name)[0] or ''
        if mime not in ALL_ALLOWED:
            return JsonResponse({'error': 'Тип файла не поддерживается'}, status=400)
        if uploaded.size > MAX_FILE_SIZE:
            return JsonResponse({'error': 'Файл слишком большой (макс. 10 МБ)'}, status=400)
        msg.file = uploaded
        msg.file_name = uploaded.name
        msg.file_size = uploaded.size
        msg.file_type = _get_file_type(mime)

    msg.save()
    return JsonResponse(_msg_to_dict(msg, request.user))


@login_required
def chat_poll(request, conv_id):
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    _update_online(request.user)
    since_id = int(request.GET.get('since', 0))

    new_msgs = (
        conv.messages
        .filter(pk__gt=since_id)
        .select_related('sender', 'sender__profile')
        .order_by('created_at')
    )
    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    # Online statuses of conv participants
    online = {}
    for p in conv.participants.select_related('profile').all():
        online[p.pk] = p.profile.is_online if hasattr(p, 'profile') else False

    total_unread = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    is_muted = _get_mute(request.user, conv)

    return JsonResponse({
        'messages': [_msg_to_dict(m, request.user) for m in new_msgs],
        'total_unread': total_unread,
        'online': online,
        'is_muted': is_muted,
    })


@login_required
def chat_unread(request):
    _update_online(request.user)
    count = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({'unread': count})


@login_required
@require_POST
def chat_mute(request, conv_id):
    """Toggle mute for a conversation."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    settings_obj, _ = ConversationSettings.objects.get_or_create(
        user=request.user, conversation=conv
    )
    settings_obj.is_muted = not settings_obj.is_muted
    settings_obj.save(update_fields=['is_muted'])
    return JsonResponse({'is_muted': settings_obj.is_muted})


@login_required
@require_POST
def chat_edit(request, msg_id):
    msg = get_object_or_404(Message, pk=msg_id, sender=request.user)
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
    except Exception:
        text = ''
    if not text:
        return JsonResponse({'error': 'empty'}, status=400)
    msg.text = text
    msg.save(update_fields=['text'])
    return JsonResponse({'id': msg.pk, 'text': msg.text})


@login_required
@require_POST
def chat_delete(request, msg_id):
    msg = get_object_or_404(Message, pk=msg_id, sender=request.user)
    if msg.file:
        try:
            from django.core.files.storage import default_storage
            default_storage.delete(msg.file.name)
        except Exception:
            pass
    msg.delete()
    return JsonResponse({'id': msg_id, 'deleted': True})
