import json
import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q, Max, Count
from django.core.files.storage import default_storage
from ..models import Conversation, Message

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain', 'text/csv',
    ],
    'archive': ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed'],
}
ALL_ALLOWED = sum(ALLOWED_TYPES.values(), [])


def _get_file_type(mime):
    for ftype, mimes in ALLOWED_TYPES.items():
        if mime in mimes:
            return ftype
    return 'file'


def _msg_to_dict(msg, current_user):
    d = {
        'id': msg.pk,
        'text': msg.text,
        'sender': msg.sender.username,
        'sender_id': msg.sender.pk,
        'created_at': msg.created_at.strftime('%H:%M'),
        'date': msg.created_at.strftime('%d.%m.%Y'),
        'mine': msg.sender_id == current_user.pk,
    }
    if msg.file:
        d['file'] = {
            'url': msg.file.url,
            'name': msg.file_name or os.path.basename(msg.file.name),
            'size': msg.file_size or 0,
            'type': msg.file_type or 'file',
        }
    return d


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
        convs_data.append({'conv': c, 'other': other, 'last': last, 'unread': unread})
    return convs_data


@login_required
def chat_list(request):
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
    other = get_object_or_404(User, pk=user_id)
    if other == request.user:
        return redirect('chat_list')
    conv = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=other)
        .first()
    )
    if not conv:
        conv = Conversation.objects.create()
        conv.participants.add(request.user, other)
    return redirect('chat_room', conv_id=conv.pk)


@login_required
def chat_room(request, conv_id):
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    other = conv.other_participant(request.user)
    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    messages_qs = conv.messages.select_related('sender').order_by('created_at')
    convs_data = _sidebar_data(request, active_conv_id=conv.pk)
    all_users = User.objects.exclude(pk=request.user.pk).order_by('username')
    total_unread = sum(c['unread'] for c in convs_data)
    return render(request, 'projects/chat/room.html', {
        'conv': conv,
        'other': other,
        'messages_qs': messages_qs,
        'convs_data': convs_data,
        'all_users': all_users,
        'total_unread': total_unread,
    })


@login_required
@require_POST
def chat_send(request, conv_id):
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)

    # Handle multipart (file) or JSON (text/sticker)
    if request.content_type and 'multipart' in request.content_type:
        text = request.POST.get('text', '').strip()
        uploaded = request.FILES.get('file')
    else:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
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
    since_id = int(request.GET.get('since', 0))
    new_msgs = (
        conv.messages
        .filter(pk__gt=since_id)
        .select_related('sender')
        .order_by('created_at')
    )
    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    total_unread = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({
        'messages': [_msg_to_dict(m, request.user) for m in new_msgs],
        'total_unread': total_unread,
    })


@login_required
def chat_unread(request):
    count = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({'unread': count})


@login_required
@require_POST
def chat_edit(request, msg_id):
    """Edit own message text."""
    msg = get_object_or_404(Message, pk=msg_id, sender=request.user)
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = ''
    if not text:
        return JsonResponse({'error': 'empty'}, status=400)
    if len(text) > 4000:
        return JsonResponse({'error': 'too_long'}, status=400)
    msg.text = text
    msg.save(update_fields=['text'])
    return JsonResponse({'id': msg.pk, 'text': msg.text})


@login_required
@require_POST
def chat_delete(request, msg_id):
    """Delete own message."""
    msg = get_object_or_404(Message, pk=msg_id, sender=request.user)
    # Delete file from storage if exists
    if msg.file:
        try:
            default_storage.delete(msg.file.name)
        except Exception:
            pass
    msg.delete()
    return JsonResponse({'id': msg_id, 'deleted': True})
