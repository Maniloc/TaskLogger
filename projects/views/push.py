"""
Web Push notification views:
  - push_subscribe   POST  — save/update browser subscription
  - push_unsubscribe POST  — delete subscription
  - push_vapid_key   GET   — return public VAPID key for browser
"""
import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import PushSubscription

logger = logging.getLogger(__name__)


@login_required
def push_vapid_key(request):
    """Return VAPID public key so the browser can subscribe."""
    return JsonResponse({'public_key': settings.VAPID_PUBLIC_KEY})


@login_required
@require_POST
def push_subscribe(request):
    """Save or update a push subscription for this user."""
    try:
        data     = json.loads(request.body)
        endpoint = data['endpoint']
        keys     = data['keys']
        p256dh   = keys['p256dh']
        auth     = keys['auth']
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid data'}, status=400)

    # Keep one sub per endpoint; update if re-subscribing
    sub, created = PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={'p256dh': p256dh, 'auth': auth},
    )
    return JsonResponse({'subscribed': True, 'created': created})


@login_required
@require_POST
def push_unsubscribe(request):
    """Remove a push subscription."""
    try:
        data     = json.loads(request.body)
        endpoint = data['endpoint']
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid data'}, status=400)

    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'unsubscribed': True})


def send_push(user, title, body, url='/chat/', tag='chat-message'):
    """
    Send a push notification to all of user's subscriptions.
    Called from chat_send after a message is saved.
    """
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY_PEM:
        return  # VAPID not configured

    from pywebpush import webpush, WebPushException

    subs = PushSubscription.objects.filter(user=user)
    if not subs.exists():
        return

    payload = json.dumps({
        'title': title,
        'body':  body,
        'url':   url,
        'tag':   tag,
        'icon':  '/static/projects/favicon.ico',
    })

    dead = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys':     {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PEM,
                vapid_claims={
                    'sub': f'mailto:{settings.VAPID_ADMIN_EMAIL}',
                },
            )
        except WebPushException as e:
            status = e.response.status_code if e.response else 0
            if status in (404, 410):        # subscription expired / gone
                dead.append(sub.pk)
            else:
                logger.warning('WebPush failed for user %s: %s', user.pk, e)
        except Exception as e:
            logger.warning('WebPush unexpected error for user %s: %s', user.pk, e)

    if dead:
        PushSubscription.objects.filter(pk__in=dead).delete()
