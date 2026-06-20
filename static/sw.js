self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim());
});

function parsePushData(event) {
  var data = { title: 'BlackSquare', body: 'Новое уведомление', url: '/dashboard' };
  if (!event.data) return data;
  try {
    return Object.assign(data, event.data.json());
  } catch (err1) {
    try {
      data.body = event.data.text() || data.body;
    } catch (err2) {}
  }
  return data;
}

function notifyClients(payload) {
  return self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    list.forEach(function (client) {
      client.postMessage({ type: 'bs-push', data: payload });
    });
  });
}

self.addEventListener('push', function (e) {
  var data = parsePushData(e);
  var origin = self.location.origin;
  var targetUrl = data.url || '/dashboard';
  if (targetUrl.indexOf('http') !== 0) targetUrl = origin + targetUrl;
  var options = {
    body: data.body || 'Новое уведомление',
    icon: origin + '/static/icon-192.png',
    badge: origin + '/static/icon-192.png',
    tag: data.tag || ('bs-' + Date.now()),
    renotify: true,
    requireInteraction: true,
    vibrate: [200, 100, 200],
    silent: false,
    data: { url: targetUrl },
  };
  e.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || 'BlackSquare', options),
      notifyClients({ title: data.title, body: data.body, url: targetUrl }),
    ]).catch(function () {
      return self.registration.showNotification('BlackSquare', {
        body: data.body || 'Новое уведомление',
        icon: origin + '/static/icon-192.png',
        tag: 'bs-fallback-' + Date.now(),
        data: { url: targetUrl },
      });
    })
  );
});

self.addEventListener('pushsubscriptionchange', function (e) {
  e.waitUntil(
    notifyClients({ type: 'resubscribe', title: 'BlackSquare', body: 'Обновите push в профиле' })
  );
});

self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var target = (e.notification.data && e.notification.data.url) || '/dashboard';
  var url = new URL(target, self.location.origin).href;
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        var c = list[i];
        if ('focus' in c) {
          return c.focus().then(function () {
            if (typeof c.navigate === 'function') return c.navigate(url);
          });
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
