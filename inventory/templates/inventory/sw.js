/*
 * 2ndHand Staging Hub - Root Service Worker (/sw.js)
 * Minimal pass-through Service Worker for PWA installability and Web Push Notifications.
 * Zero HTML / CSRF caching by design to guarantee real-time inventory state.
 */

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Pass-through fetch handler: required for PWA installability criteria,
// while strictly delegating all HTTP/HTML/CSRF requests directly to the network.
self.addEventListener('fetch', (event) => {
  return;
});

// Web Push Notification handler
self.addEventListener('push', (event) => {
  let payload = {
    title: '2ndHand Staging',
    body: 'New activity in the inventory hub.',
    url: '/',
    tag: '2ndhand-general',
    icon: '/static/inventory/icons/icon-192.png',
    badge: '/static/inventory/icons/icon-192.png',
    badge_count: null,
  };

  if (event.data) {
    try {
      const parsed = event.data.json();
      payload = Object.assign({}, payload, parsed);
    } catch (err) {
      payload.body = event.data.text() || payload.body;
    }
  }

  const options = {
    body: payload.body,
    icon: payload.icon || '/static/inventory/icons/icon-192.png',
    badge: payload.badge || '/static/inventory/icons/icon-192.png',
    tag: payload.tag || '2ndhand-general',
    renotify: true,
    data: {
      url: payload.url || '/',
    },
  };

  const tasks = [self.registration.showNotification(payload.title, options)];

  if (
    typeof payload.badge_count === 'number' &&
    self.navigator &&
    typeof self.navigator.setAppBadge === 'function'
  ) {
    if (payload.badge_count > 0) {
      tasks.push(self.navigator.setAppBadge(payload.badge_count).catch(() => {}));
    } else if (typeof self.navigator.clearAppBadge === 'function') {
      tasks.push(self.navigator.clearAppBadge().catch(() => {}));
    }
  }

  event.waitUntil(Promise.all(tasks));
});

// Notification click deep-linking handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const targetPath =
    event.notification.data && event.notification.data.url
      ? event.notification.data.url
      : '/';
  const targetUrl = new URL(targetPath, self.location.origin).href;

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url === targetUrl && 'focus' in client) {
            return client.focus();
          }
        }
        for (const client of windowClients) {
          if (
            client.url.startsWith(self.location.origin) &&
            'focus' in client &&
            'navigate' in client
          ) {
            return client.navigate(targetUrl).then((navigatedClient) => {
              return navigatedClient ? navigatedClient.focus() : null;
            });
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
        return null;
      })
  );
});
