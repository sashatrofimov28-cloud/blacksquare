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
    navigator.serviceWorker.register('/sw.js?v=11', { scope: '/' }).then(function (reg) {
      reg.update();
    }).catch(function () {});
  }

  /* --- Push notifications --- */
  const vapidKey = window.BS_VAPID_PUBLIC_KEY;
  const PUSH_VERSION = window.BS_PUSH_KEY_VERSION || 1;
  const pushStatus = document.getElementById('pushStatus');
  const pushEnableBtn = document.getElementById('pushEnableBtn');
  const pushRetryBtn = document.getElementById('pushRetryBtn');
  const pushHelpBtn = document.getElementById('pushHelpBtn');
  const pushHelp = document.getElementById('pushHelp');
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
    if (pushRetryBtn) pushRetryBtn.style.display = state === 'blocked' ? '' : 'none';
    if (pushHelpBtn) pushHelpBtn.style.display = state === 'blocked' ? '' : 'none';
    if (pushDisableBtn) pushDisableBtn.style.display = state === 'on' ? '' : 'none';
    if (pushTestBtn) pushTestBtn.style.display = state === 'on' ? '' : 'none';
    if (state !== 'blocked' && pushHelp) pushHelp.hidden = true;
  }

  async function getSwReg() {
    if (!('serviceWorker' in navigator)) return null;
    return navigator.serviceWorker.ready;
  }

  async function clearBrowserPushSubscription() {
    const reg = await getSwReg();
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      try { await sub.unsubscribe(); } catch (e) {}
    }
    localStorage.removeItem('bs_vapid_key');
    localStorage.removeItem('bs_push_version');
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
      setPushUi('blocked', 'Уведомления выключены в браузере. Разрешите их в настройках сайта, затем нажмите «Проверить снова».');
      return;
    }
    const reg = await getSwReg();
    if (!reg) {
      setPushUi('off', 'Сервис-воркер не готов. Обновите страницу.');
      return;
    }
    const sub = await reg.pushManager.getSubscription();
    const storedKey = localStorage.getItem('bs_vapid_key');
    const storedVersion = parseInt(localStorage.getItem('bs_push_version') || '0', 10);
    const needsRenew = sub && (
      storedVersion < PUSH_VERSION ||
      !storedKey ||
      storedKey !== vapidKey
    );
    if (needsRenew) {
      await clearBrowserPushSubscription();
      setPushUi('off', 'Нужно обновить подписку. Нажмите «Включить уведомления».');
      return;
    }
    if (sub) {
      try {
        await fetch('/api/push-subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subscription: sub.toJSON(), sync: true }),
        });
        const status = await fetch('/api/push-status').then(function (r) { return r.json(); });
        if (status.subscribed) {
          setPushUi('on', 'Уведомления включены. Вы будете получать оповещения о новых записях.');
          return;
        }
      } catch (e) {}
      await clearBrowserPushSubscription();
      setPushUi('off', 'Подписка не активна. Нажмите «Включить уведомления».');
      return;
    }
    if (Notification.permission === 'granted') {
      setPushUi('off', 'Разрешение есть, но подписка не активна. Нажмите «Включить».');
    } else {
      setPushUi('off', 'Уведомления выключены. Нажмите кнопку ниже — придут оповещения о новых записях.');
    }
  }

  async function enablePush() {
    if (!vapidKey) {
      setPushUi('unsupported', 'Push не настроен на сервере. Обратитесь к администратору.');
      return;
    }
    try {
      const reg = await getSwReg();
      if (!reg) throw new Error('no sw');
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setPushUi('blocked', perm === 'denied'
          ? 'Уведомления выключены в браузере. Нажмите «Как включить» — там пошаговая инструкция.'
          : 'Разрешение не получено. Попробуйте ещё раз или включите уведомления в настройках браузера.');
        return;
      }
      const oldSub = await reg.pushManager.getSubscription();
      if (oldSub) {
        try { await oldSub.unsubscribe(); } catch (e) {}
      }
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
      const res = await fetch('/api/push-subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub.toJSON() }),
      });
      const data = await res.json();
      if (data.ok && data.test_sent) {
        localStorage.setItem('bs_vapid_key', vapidKey);
        localStorage.setItem('bs_push_version', String(PUSH_VERSION));
        setPushUi('on', 'Уведомления включены! Тестовое сообщение отправлено.');
      } else {
        await clearBrowserPushSubscription();
        setPushUi('off', data.error || 'Не удалось подключить уведомления. Попробуйте ещё раз.');
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
      localStorage.removeItem('bs_vapid_key');
      localStorage.removeItem('bs_push_version');
      setPushUi('off', 'Уведомления отключены.');
    } catch (e) {
      setPushUi('off', 'Подписка снята.');
    }
  }

  async function testPush() {
    try {
      const reg = await getSwReg();
      const sub = reg && (await reg.pushManager.getSubscription());
      const res = await fetch('/api/push-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: sub ? sub.toJSON() : null }),
      });
      const data = await res.json();
      if (pushStatus) {
        if (data.ok) {
          setPushUi('on', 'Тестовое уведомление отправлено. Проверьте экран телефона.');
        } else {
          setPushUi('on', data.error || 'Ошибка отправки');
        }
      }
    } catch (e) {
      if (pushStatus) pushStatus.textContent = 'Ошибка: ' + (e.message || 'не удалось отправить тест');
    }
  }

  function initMasterPicker() {
    const picker = document.getElementById('masterPicker');
    if (!picker) return;
    const masters = window.BS_MASTERS || [];
    const initial = (window.BS_INITIAL_MASTERS || []).map(String);
    const select = document.getElementById('masterSelect');
    const addBtn = document.getElementById('addMasterBtn');
    const chips = document.getElementById('masterChips');
    const hidden = document.getElementById('masterHiddenInputs');
    const emptyHint = document.getElementById('masterEmptyHint');
    const formId = picker.dataset.formId;
    const form = formId ? document.getElementById(formId) : picker.closest('form');
    const selected = new Set();

    masters.forEach(function (m) {
      const opt = document.createElement('option');
      opt.value = String(m.id);
      opt.textContent = m.name;
      select.appendChild(opt);
    });

    function syncEmptyHint() {
      if (emptyHint) emptyHint.hidden = selected.size > 0;
    }

    function showMasterError(show) {
      picker.classList.toggle('field-error', !!show);
      const hint = picker.querySelector('.master-required-hint');
      if (hint) hint.hidden = !show;
    }

    function addMaster(id) {
      const sid = String(id);
      if (!sid || selected.has(sid)) return;
      const master = masters.find(function (m) { return String(m.id) === sid; });
      if (!master) return;
      selected.add(sid);
      const chip = document.createElement('span');
      chip.className = 'master-chip';
      chip.dataset.id = sid;
      chip.innerHTML = master.name + ' <button type="button" class="master-chip-remove" aria-label="Убрать">×</button>';
      chip.querySelector('.master-chip-remove').addEventListener('click', function () {
        selected.delete(sid);
        chip.remove();
        const input = hidden.querySelector('input[data-id="' + sid + '"]');
        if (input) input.remove();
        syncEmptyHint();
        showMasterError(false);
      });
      chips.appendChild(chip);
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'employee_ids';
      input.value = sid;
      input.dataset.id = sid;
      hidden.appendChild(input);
      select.value = '';
      syncEmptyHint();
      showMasterError(false);
    }

    if (addBtn) {
      addBtn.addEventListener('click', function () {
        if (!select.value) {
          showMasterError(true);
          select.focus();
          return;
        }
        addMaster(select.value);
      });
    }

    initial.forEach(addMaster);

    if (form) {
      form.addEventListener('submit', function (e) {
        if (!selected.size) {
          e.preventDefault();
          showMasterError(true);
          picker.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    }
  }

  if (pushEnableBtn) pushEnableBtn.addEventListener('click', enablePush);
  if (pushRetryBtn) pushRetryBtn.addEventListener('click', async function () {
    await refreshPushStatus();
    if (Notification.permission === 'granted') {
      const reg = await getSwReg();
      const sub = reg && (await reg.pushManager.getSubscription());
      if (!sub) await enablePush();
    }
  });
  if (pushHelpBtn && pushHelp) {
    pushHelpBtn.addEventListener('click', function () {
      pushHelp.hidden = !pushHelp.hidden;
      pushHelpBtn.textContent = pushHelp.hidden ? 'Как включить' : 'Скрыть инструкцию';
    });
  }
  if (pushDisableBtn) pushDisableBtn.addEventListener('click', disablePush);
  if (pushTestBtn) pushTestBtn.addEventListener('click', testPush);

  if (document.querySelector('.app-shell')) {
    window.addEventListener('load', function () {
      closeSidebar();
      refreshPushStatus();
      initMasterPicker();
      const tabs = document.getElementById('mobileTabs');
      if (tabs) {
        const active = tabs.querySelector('a.active');
        if (active) active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
      }
    });
  }
})();
