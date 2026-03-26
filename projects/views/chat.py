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
from django.utils.timezone import localtime
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
        'created_at': localtime(msg.created_at).strftime('%H:%M'),
        'date': localtime(msg.created_at).strftime('%d.%m.%Y'),
        'mine': msg.sender_id == current_user.pk,
        'avatar': av,
        'is_read':   msg.is_read,
        'reply_to':  {
            'id': msg.reply_to.pk,
            'text': msg.reply_to.text[:80],
            'sender': _display_name(msg.reply_to.sender),
        } if msg.reply_to_id else None,
        'is_edited':  msg.is_edited,
        'edited_at':  localtime(msg.edited_at).strftime('%H:%M') if msg.edited_at else None,
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

    # Handle reply_to
    reply_id = data.get('reply_to') if not uploaded else request.POST.get('reply_to')
    reply_msg = None
    if reply_id:
        reply_msg = Message.objects.filter(pk=int(reply_id), conversation=conv).first()

    msg = Message(conversation=conv, sender=request.user, text=text, reply_to=reply_msg)

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
        try:
            prof = p.profile
            is_on = prof.is_online
            last = localtime(prof.last_seen).strftime('%d.%m.%Y в %H:%M') if prof.last_seen and not is_on else None
            online[p.pk] = {'online': is_on, 'last_seen': last}
        except Exception:
            online[p.pk] = {'online': False, 'last_seen': None}

    total_unread = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    is_muted = _get_mute(request.user, conv)

    # IDs of MY messages that are now read (so JS can update tick to ✓✓)
    read_ids = list(
        conv.messages
        .filter(sender=request.user, is_read=True, pk__gt=since_id - 200)
        .values_list('pk', flat=True)[:50]
    )

    return JsonResponse({
        'messages': [_msg_to_dict(m, request.user) for m in new_msgs],
        'total_unread': total_unread,
        'online': online,
        'is_muted': is_muted,
        'read_ids': read_ids,
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
    msg.text      = text
    msg.is_edited  = True
    msg.edited_at  = timezone.now()
    msg.save(update_fields=['text', 'is_edited', 'edited_at'])
    return JsonResponse({
        'id': msg.pk,
        'text': msg.text,
        'is_edited': True,
        'edited_at': localtime(msg.edited_at).strftime('%H:%M'),
    })


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


@login_required
@require_POST
def chat_clear(request, conv_id):
    """Delete all messages in conversation (for current user it just clears their view)."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    # Only creator / DM participant can clear
    conv.messages.all().delete()
    return JsonResponse({'cleared': True})


@login_required
@require_POST  
def chat_leave(request, conv_id):
    """Leave / delete conversation."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    if conv.is_group:
        # Just leave the group
        conv.participants.remove(request.user)
        # If no participants left, delete
        if conv.participants.count() == 0:
            conv.delete()
    else:
        # For DM: delete conversation and all messages
        conv.messages.all().delete()
        conv.delete()
    return JsonResponse({'left': True})


@login_required
@require_POST
def chat_add_member(request, conv_id):
    """Add user to group conversation."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    if not conv.is_group:
        return JsonResponse({'error': 'Только для бесед'}, status=400)
    # Only creator can add
    if conv.created_by_id and conv.created_by_id != request.user.pk:
        return JsonResponse({'error': 'Только создатель может добавлять участников'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = int(data.get('user_id', 0))
    except Exception:
        return JsonResponse({'error': 'Неверные данные'}, status=400)
    
    user = get_object_or_404(User, pk=user_id)
    if conv.participants.filter(pk=user_id).exists():
        return JsonResponse({'error': 'Пользователь уже в беседе'}, status=400)
    
    conv.participants.add(user)
    # Notify in chat
    try:
        adder_name = _display_name(request.user)
        new_name   = _display_name(user)
        Message.objects.create(
            conversation=conv, sender=request.user,
            text=f'➕ {adder_name} добавил(а) {new_name} в беседу'
        )
    except Exception:
        pass
    
    try:
        av = user.profile
        avatar = {'type': 'img', 'url': av.avatar.url} if av.avatar else {
            'type': 'initials', 'text': av.initials or user.username[:2].upper(),
            'color': av.avatar_color or ''
        }
    except Exception:
        avatar = {'type': 'initials', 'text': user.username[:1].upper(), 'color': ''}
    
    return JsonResponse({
        'user_id': user.pk,
        'username': user.username,
        'display_name': _display_name(user),
        'avatar': avatar,
    })


@login_required
@require_POST
def chat_forward(request, conv_id):
    """Forward a message to another conversation."""
    source_conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    try:
        data = json.loads(request.body)
        msg_id  = int(data.get('msg_id', 0))
        target_ids = data.get('target_ids', [])
    except Exception:
        return JsonResponse({'error': 'bad data'}, status=400)

    orig = get_object_or_404(Message, pk=msg_id, conversation=source_conv)
    sent = []
    for tid in target_ids[:5]:  # max 5 conversations
        target = Conversation.objects.filter(pk=tid, participants=request.user).first()
        if not target:
            continue
        prefix = '[fwd] ' + _display_name(orig.sender) + ':' + chr(10)
        fwd = Message.objects.create(
            conversation=target,
            sender=request.user,
            text=prefix + orig.text if orig.text else '',
        )
        if orig.file:
            fwd.file      = orig.file
            fwd.file_name = orig.file_name
            fwd.file_size = orig.file_size
            fwd.file_type = orig.file_type
            fwd.save(update_fields=['file','file_name','file_size','file_type'])
        sent.append(tid)
    return JsonResponse({'forwarded': len(sent), 'to': sent})


@login_required
def chat_search(request, conv_id):
    """Search messages in a conversation."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    q = request.GET.get('q', '').strip()
    results = []
    if q and len(q) >= 2:
        msgs = (
            conv.messages
            .filter(text__icontains=q)
            .select_related('sender', 'sender__profile')
            .order_by('-created_at')[:30]
        )
        results = [_msg_to_dict(m, request.user) for m in msgs]
    return JsonResponse({'results': results, 'query': q})
