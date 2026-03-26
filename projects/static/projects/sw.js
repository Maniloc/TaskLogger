// ── TaskLogger Service Worker ──
// Handles push notifications when the page is not open.

self.addEventListener('push', function(event) {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: 'TaskLogger', body: event.data.text() };
  }

  const title   = data.title || 'Новое сообщение';
  const options = {
    body:  data.body  || '',
    icon:  data.icon  || '/static/projects/favicon.ico',
    badge: data.badge || '/static/projects/favicon.ico',
    tag:   data.tag   || 'chat-message',
    data:  { url: data.url || '/chat/' },
    renotify:  true,
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/chat/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(list) {
      for (const client of list) {
        if (client.url.includes('/chat/') && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
