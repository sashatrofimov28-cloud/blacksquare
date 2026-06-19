(function () {
  const menuBtn = document.getElementById('menuBtn');
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  const MOBILE_MQ = window.matchMedia('(max-width: 900px)');

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('open');
    if (backdrop) backdrop.classList.add('open');
    document.body.classList.add('menu-open');
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    document.body.classList.remove('menu-open');
  }

  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
  }

  if (sidebar) {
    sidebar.querySelectorAll('nav a').forEach(function (link) {
      link.addEventListener('click', function () {
        if (isMobile()) closeSidebar();
      });
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  MOBILE_MQ.addEventListener('change', function () {
    if (!isMobile()) closeSidebar();
  });

  if (isMobile()) closeSidebar();

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
      closeSidebar();
      setTimeout(subscribePush, 1500);
      const tabs = document.getElementById('mobileTabs');
      if (tabs) {
        const active = tabs.querySelector('a.active');
        if (active) active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
      }
    });
  }
})();
