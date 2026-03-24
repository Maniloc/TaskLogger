import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Max, OuterRef, Subquery, Count
from django.utils import timezone
from ..models import Conversation, Message


@login_required
def chat_list(request):
    """List all conversations for current user."""
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related('participants')
        .annotate(last_msg_time=Max('messages__created_at'))
        .order_by('-last_msg_time')
    )
    # Add unread counts and last messages
    convs_data = []
    for conv in conversations:
        other = conv.other_participant(request.user)
        last = conv.last_message()
        unread = conv.unread_count(request.user)
        convs_data.append({
            'conv': conv,
            'other': other,
            'last': last,
            'unread': unread,
        })

    # Users available to start conversation with
    all_users = User.objects.exclude(pk=request.user.pk).order_by('username')

    total_unread = sum(c['unread'] for c in convs_data)

    return render(request, 'projects/chat/list.html', {
        'convs_data': convs_data,
        'all_users': all_users,
        'total_unread': total_unread,
    })


@login_required
def chat_open(request, user_id):
    """Open or create conversation with a specific user."""
    other = get_object_or_404(User, pk=user_id)
    if other == request.user:
        return redirect('chat_list')

    # Find existing conversation between these two users
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
    """Chat room view."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    other = conv.other_participant(request.user)

    # Mark all messages from other user as read
    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_qs = conv.messages.select_related('sender').order_by('created_at')

    # All conversations for sidebar
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related('participants')
        .annotate(last_msg_time=Max('messages__created_at'))
        .order_by('-last_msg_time')
    )
    convs_data = []
    for c in conversations:
        o = c.other_participant(request.user)
        last = c.last_message()
        unread = c.unread_count(request.user) if c.pk != conv.pk else 0
        convs_data.append({'conv': c, 'other': o, 'last': last, 'unread': unread})

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
    """Send a message (AJAX)."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = request.POST.get('text', '').strip()

    if not text:
        return JsonResponse({'error': 'empty'}, status=400)
    if len(text) > 4000:
        return JsonResponse({'error': 'too_long'}, status=400)

    msg = Message.objects.create(
        conversation=conv,
        sender=request.user,
        text=text,
    )
    return JsonResponse({
        'id': msg.pk,
        'text': msg.text,
        'sender': msg.sender.username,
        'sender_id': msg.sender.pk,
        'created_at': msg.created_at.strftime('%H:%M'),
        'date': msg.created_at.strftime('%d.%m.%Y'),
    })


@login_required
def chat_poll(request, conv_id):
    """Poll for new messages since a given message id."""
    conv = get_object_or_404(Conversation, pk=conv_id, participants=request.user)
    since_id = int(request.GET.get('since', 0))

    new_msgs = (
        conv.messages
        .filter(pk__gt=since_id)
        .select_related('sender')
        .order_by('created_at')
    )

    # Mark incoming as read
    new_msgs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    data = [{
        'id': m.pk,
        'text': m.text,
        'sender': m.sender.username,
        'sender_id': m.sender.pk,
        'created_at': m.created_at.strftime('%H:%M'),
        'date': m.created_at.strftime('%d.%m.%Y'),
        'mine': m.sender_id == request.user.pk,
    } for m in new_msgs]

    # Also return global unread count for nav badge
    total_unread = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )

    return JsonResponse({'messages': data, 'total_unread': total_unread})


@login_required
def chat_unread(request):
    """Quick endpoint for nav badge unread count."""
    count = (
        Message.objects
        .filter(conversation__participants=request.user, is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({'unread': count})
