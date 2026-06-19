(function () {
  const menuBtn = document.getElementById('menuBtn');
  const sidebar = document.getElementById('sidebar');
  const mainWrap = document.querySelector('.main-wrap');
  if (menuBtn && sidebar && mainWrap) {
    menuBtn.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      mainWrap.classList.toggle('expanded');
    });
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  }

  const vapidKey = window.BS_VAPID_PUBLIC_KEY;
  if (!vapidKey || !('PushManager' in window)) return;

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  async function subscribePush() {
    try {
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        const perm = await Notification.requestPermission();
        if (perm !== 'granted') return;
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidKey),
        });
      }
      await fetch('/api/push-subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub.toJSON() }),
      });
    } catch (e) {
      console.warn('Push subscribe failed', e);
    }
  }

  if (document.querySelector('.app-shell')) {
    window.addEventListener('load', function () {
      setTimeout(subscribePush, 1500);
    });
  }
})();
