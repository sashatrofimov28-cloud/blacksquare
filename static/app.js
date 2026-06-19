(function () {
  const menuBtn = document.getElementById('menuBtn');
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  const MOBILE_MQ = window.matchMedia('(max-width: 1024px)');

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function openSidebar() {
    if (!sidebar || !isMobile()) return;
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
      e.preventDefault();
      e.stopPropagation();
      if (sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    });
  }

  if (backdrop) backdrop.addEventListener('click', closeSidebar);

  if (sidebar) {
    sidebar.querySelectorAll('nav a').forEach(function (link) {
      link.addEventListener('click', function () {
        closeSidebar();
      });
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  MOBILE_MQ.addEventListener('change', function () {
    if (!isMobile()) closeSidebar();
  });

  closeSidebar();

  /* --- Service Worker --- */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js?v=5', { scope: '/' }).then(function (reg) {
      reg.update();
    }).catch(function () {});
  }

  /* --- Push notifications --- */
  const vapidKey = window.BS_VAPID_PUBLIC_KEY;
  const pushStatus = document.getElementById('pushStatus');
  const pushEnableBtn = document.getElementById('pushEnableBtn');
  const pushDisableBtn = document.getElementById('pushDisableBtn');
  const pushTestBtn = document.getElementById('pushTestBtn');

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  function setPushUi(state, message) {
    if (!pushStatus) return;
    pushStatus.textContent = message;
    pushStatus.className = 'hint push-status push-' + state;
    if (pushEnableBtn) pushEnableBtn.style.display = (state === 'on' || state === 'blocked' || state === 'unsupported') ? 'none' : '';
    if (pushDisableBtn) pushDisableBtn.style.display = state === 'on' ? '' : 'none';
    if (pushTestBtn) pushTestBtn.style.display = state === 'on' ? '' : 'none';
  }

  async function getSwReg() {
    if (!('serviceWorker' in navigator)) return null;
    return navigator.serviceWorker.ready;
  }

  async function refreshPushStatus() {
    if (!pushStatus) return;
    if (!vapidKey) {
      setPushUi('unsupported', 'Push не настроен на сервере. Обратитесь к администратору.');
      return;
    }
    if (!('Notification' in window) || !('PushManager' in window)) {
      setPushUi('unsupported', 'Браузер не поддерживает push-уведомления.');
      return;
    }
    if (Notification.permission === 'denied') {
      setPushUi('blocked', 'Уведомления заблокированы. Разрешите их в настройках браузера / телефона.');
      return;
    }
    const reg = await getSwReg();
    if (!reg) {
      setPushUi('off', 'Сервис-воркер не готов. Обновите страницу.');
      return;
    }
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      setPushUi('on', 'Уведомления включены. Вы будете получать оповещения о новых записях.');
    } else if (Notification.permission === 'granted') {
      setPushUi('off', 'Разрешение есть, но подписка не активна. Нажмите «Включить».');
    } else {
      setPushUi('off', 'Уведомления выключены. Нажмите кнопку ниже — придут оповещения о новых записях.');
    }
  }

  async function enablePush() {
    if (!vapidKey) return;
    try {
      const reg = await getSwReg();
      if (!reg) throw new Error('no sw');
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setPushUi('blocked', 'Вы отклонили уведомления. Можно включить в настройках браузера.');
        return;
      }
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidKey),
        });
      }
      const res = await fetch('/api/push-subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub.toJSON() }),
      });
      const data = await res.json();
      if (data.ok) {
        setPushUi('on', 'Уведомления включены!');
        if (data.test_sent) {
          setPushUi('on', 'Уведомления включены! Тестовое сообщение отправлено.');
        }
      } else {
        setPushUi('off', data.error || 'Не удалось сохранить подписку.');
      }
    } catch (e) {
      setPushUi('off', 'Ошибка: ' + (e.message || 'не удалось подключить уведомления'));
    }
  }

  async function disablePush() {
    try {
      const reg = await getSwReg();
      const sub = reg && (await reg.pushManager.getSubscription());
      if (sub) {
        await fetch('/api/push-unsubscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint }),
        });
        await sub.unsubscribe();
      }
      setPushUi('off', 'Уведомления отключены.');
    } catch (e) {
      setPushUi('off', 'Подписка снята.');
    }
  }

  async function testPush() {
    const res = await fetch('/api/push-test', { method: 'POST' });
    const data = await res.json();
    if (pushStatus) {
      pushStatus.textContent = data.ok ? 'Тестовое уведомление отправлено.' : (data.error || 'Ошибка отправки');
    }
  }

  if (pushEnableBtn) pushEnableBtn.addEventListener('click', enablePush);
  if (pushDisableBtn) pushDisableBtn.addEventListener('click', disablePush);
  if (pushTestBtn) pushTestBtn.addEventListener('click', testPush);

  if (document.querySelector('.app-shell')) {
    window.addEventListener('load', function () {
      closeSidebar();
      refreshPushStatus();
      const tabs = document.getElementById('mobileTabs');
      if (tabs) {
        const active = tabs.querySelector('a.active');
        if (active) active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
      }
    });
  }
})();
