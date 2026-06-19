self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (e) {
  let data = { title: 'BlackSquare', body: 'Новое уведомление', url: '/dashboard' };
  try {
    if (e.data) data = Object.assign(data, e.data.json());
  } catch (err) {}
  const options = {
    body: data.body,
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    tag: data.tag || 'blacksquare',
    renotify: true,
    data: { url: data.url || '/dashboard' },
  };
  e.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || '/dashboard';
  const url = new URL(target, self.location.origin).href;
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (const c of list) {
        if ('focus' in c) {
          return c.focus().then(function () {
            if (typeof c.navigate === 'function') return c.navigate(url);
          });
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
