(function () {
  const menuBtn = document.getElementById('menuBtn');
  const menuBtnBottom = document.getElementById('menuBtnBottom');
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

  if (menuBtnBottom && sidebar) {
    menuBtnBottom.addEventListener('click', function (e) {
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
    navigator.serviceWorker.register('/sw.js?v=12', { scope: '/' }).then(function (reg) {
      reg.update();
    }).catch(function () {});
    navigator.serviceWorker.addEventListener('message', function (e) {
      if (!e.data) return;
      if (e.data.type === 'bs-push') {
        if (e.data.data && e.data.data.type === 'resubscribe') {
          if (pushStatus) setPushUi('off', 'Подписка устарела. Нажмите «Включить уведомления».');
          return;
        }
        showInAppPush(e.data.data);
      }
    });
  }

  function showInAppPush(data) {
    if (!data) return;
    showLocalNotification(data.title || 'BlackSquare', data.body || '', data.url);
    var old = document.getElementById('inAppPush');
    if (old) old.remove();
    var el = document.createElement('div');
    el.id = 'inAppPush';
    el.className = 'in-app-push';
    el.innerHTML = '<b>' + (data.title || 'BlackSquare') + '</b>' + (data.body || '');
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 10000);
  }

  var lastIncomingCallId = null;

  function showIncomingCallBanner(data) {
    if (!data || !data.active) return;
    var existing = document.getElementById('incomingCallBanner');
    if (existing && String(data.id) === String(lastIncomingCallId)) return;
    lastIncomingCallId = data.id;
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.id = 'incomingCallBanner';
    el.className = 'incoming-call-banner';
    var title = data.known ? (data.client_name || 'Клиент в CRM') : 'Новый номер';
    var sub = data.phone || '';
    var actions = '<a class="incoming-call-btn primary" href="' + (data.book_url || '/calendar?book=1') + '">Записать</a>';
    if (data.card_url) {
      actions += '<a class="incoming-call-btn" href="' + data.card_url + '">Карточка</a>';
    }
    actions += '<button type="button" class="incoming-call-btn ghost" data-dismiss-call>Закрыть</button>';
    el.innerHTML =
      '<div class="incoming-call-pulse" aria-hidden="true"></div>' +
      '<div class="incoming-call-body">' +
        '<div class="incoming-call-label">Входящий звонок</div>' +
        '<div class="incoming-call-name">' + title + '</div>' +
        '<div class="incoming-call-phone">' + sub + '</div>' +
        '<div class="incoming-call-actions">' + actions + '</div>' +
      '</div>';
    document.body.appendChild(el);
    el.querySelector('[data-dismiss-call]').addEventListener('click', function () {
      fetch('/api/incoming-call/dismiss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: data.id }),
      }).catch(function () {});
      el.remove();
    });
    if (data.known && data.book_url) {
      showLocalNotification('Входящий звонок', (data.client_name || 'Клиент') + ' · ' + sub, data.book_url);
    } else if (sub) {
      showLocalNotification('Входящий звонок', sub, data.book_url || '/calendar?book=1');
    }
  }

  function pollIncomingCall() {
    fetch('/api/incoming-call', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.active) showIncomingCallBanner(data);
      })
      .catch(function () {});
  }

  function showLocalNotification(title, body, url) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      var n = new Notification(title || 'BlackSquare', {
        body: body || '',
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        tag: 'bs-local-' + Date.now(),
        renotify: true,
      });
      n.onclick = function () {
        window.focus();
        if (url) window.location.href = url;
        n.close();
      };
    } catch (e) {}
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
        showLocalNotification('BlackSquare', 'Уведомления подключены!', '/profile');
        setPushUi('on', 'Уведомления включены! Проверьте шторку уведомлений или баннер на экране.');
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
          showLocalNotification('BlackSquare — тест', 'Если вы видите это — уведомления работают.', '/dashboard');
          setPushUi('on', 'Тест отправлен. Проверьте шторку уведомлений и баннер на экране.');
        } else {
          setPushUi('on', data.error || 'Ошибка отправки');
        }
      }
    } catch (e) {
      if (pushStatus) pushStatus.textContent = 'Ошибка: ' + (e.message || 'не удалось отправить тест');
    }
  }

  function initServicePicker() {
    const picker = document.getElementById('servicePicker');
    if (!picker) return;
    const services = window.BS_SERVICES || [];
    const initial = (window.BS_INITIAL_SERVICES || []).map(String);
    const select = document.getElementById('serviceSelect');
    const addBtn = document.getElementById('addServiceBtn');
    const chips = document.getElementById('serviceChips');
    const chipGrid = document.getElementById('serviceChipGrid');
    const hidden = document.getElementById('serviceHiddenInputs');
    const emptyHint = document.getElementById('serviceEmptyHint');
    const formId = picker.dataset.formId;
    const form = formId ? document.getElementById(formId) : picker.closest('form');
    const selected = new Set();
    const uiChips = picker.dataset.ui === 'chips' && chipGrid;

    if (select && !uiChips) {
      services.forEach(function (s) {
        const opt = document.createElement('option');
        opt.value = String(s.id);
        opt.textContent = s.name + (s.price ? ' — ' + s.price + ' ₽' : '');
        select.appendChild(opt);
      });
    }

    function syncEmptyHint() {
      if (emptyHint) emptyHint.hidden = selected.size > 0;
    }

    function showServiceError(show) {
      picker.classList.toggle('field-error', !!show);
      const hint = picker.querySelector('.service-required-hint');
      if (hint) hint.hidden = !show;
    }

    function syncPriceFromServices() {
      const priceInput = document.querySelector('#manualBookingForm input[name="price"]');
      if (!priceInput || priceInput.dataset.manual === '1') return;
      let sum = 0;
      selected.forEach(function (id) {
        const service = services.find(function (s) { return String(s.id) === String(id); });
        if (service) sum += parseFloat(service.price || 0) || 0;
      });
      priceInput.value = sum > 0 ? String(Math.round(sum * 100) / 100) : '';
    }

    function syncHidden() {
      if (!hidden) return;
      hidden.innerHTML = '';
      selected.forEach(function (sid) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'service_ids';
        input.value = sid;
        input.dataset.id = sid;
        hidden.appendChild(input);
      });
    }

    function renderChipGrid() {
      if (!chipGrid) return;
      chipGrid.innerHTML = '';
      services.forEach(function (s) {
        const sid = String(s.id);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'jr-svc-chip' + (selected.has(sid) ? ' on' : '');
        btn.dataset.id = sid;
        const price = s.price != null && s.price !== '' ? String(Math.round(s.price)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : '';
        btn.innerHTML = (s.name || 'Услуга') + (price ? ' <small>' + price + '</small>' : '');
        btn.addEventListener('click', function () {
          if (selected.has(sid)) selected.delete(sid);
          else selected.add(sid);
          renderChipGrid();
          syncHidden();
          syncEmptyHint();
          showServiceError(false);
          syncPriceFromServices();
        });
        chipGrid.appendChild(btn);
      });
    }

    function addService(id) {
      const sid = String(id);
      if (!sid || selected.has(sid)) return;
      const service = services.find(function (s) { return String(s.id) === sid; });
      if (!service) return;
      selected.add(sid);
      if (uiChips) {
        renderChipGrid();
        syncHidden();
        syncEmptyHint();
        showServiceError(false);
        syncPriceFromServices();
        return;
      }
      const chip = document.createElement('span');
      chip.className = 'master-chip';
      chip.dataset.id = sid;
      chip.innerHTML = service.name + ' <button type="button" class="master-chip-remove" aria-label="Убрать">×</button>';
      chip.querySelector('.master-chip-remove').addEventListener('click', function () {
        selected.delete(sid);
        chip.remove();
        const input = hidden.querySelector('input[data-id="' + sid + '"]');
        if (input) input.remove();
        syncEmptyHint();
        showServiceError(false);
      });
      chips.appendChild(chip);
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'service_ids';
      input.value = sid;
      input.dataset.id = sid;
      hidden.appendChild(input);
      if (select) select.value = '';
      syncEmptyHint();
      showServiceError(false);
    }

    if (uiChips) {
      initial.forEach(function (id) { selected.add(String(id)); });
      renderChipGrid();
      syncHidden();
      syncPriceFromServices();
      const priceInput = document.querySelector('#manualBookingForm input[name="price"]');
      if (priceInput) {
        priceInput.addEventListener('input', function () { priceInput.dataset.manual = '1'; });
      }
    } else if (addBtn) {
      addBtn.addEventListener('click', function () {
        if (!select.value) {
          showServiceError(true);
          select.focus();
          return;
        }
        addService(select.value);
      });
      initial.forEach(addService);
    } else {
      initial.forEach(addService);
    }

    if (form) {
      form.addEventListener('submit', function (e) {
        if (!selected.size) {
          e.preventDefault();
          showServiceError(true);
          picker.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    }
  }

  function suggestedSalaryForMasters(ids) {
    const pct = Number(window.BS_MASTER_SALARY_PERCENT || 15) || 0;
    const priceEl = document.querySelector('input[name="price"], #closePriceInput');
    const price = parseFloat(priceEl && priceEl.value ? priceEl.value : 0) || 0;
    if (!ids.length || pct <= 0 || price <= 0) return {};
    const total = Math.round(price * pct) / 100;
    if (total <= 0) return {};
    const n = ids.length;
    const base = Math.round((total / n) * 100) / 100;
    const out = {};
    ids.forEach(function (id, idx) {
      out[id] = idx === 0
        ? Math.round((total - base * (n - 1)) * 100) / 100
        : base;
    });
    return out;
  }

  function recalcSalaryTotal() {
    const totalEl = document.getElementById('salaryTotal');
    if (!totalEl) return;
    let sum = 0;
    document.querySelectorAll('.salary-master-input').forEach(function (el) {
      const v = parseFloat(el.value);
      if (!isNaN(v) && v > 0) sum += v;
    });
    totalEl.textContent = Math.round(sum);
  }

  function syncSalaryMasterGrid() {
    const grid = document.getElementById('salaryMasterGrid');
    if (!grid) return;
    const masters = window.BS_MASTERS || [];
    const existing = window.BS_EXISTING_SALARIES || {};
    const values = {};
    grid.querySelectorAll('.salary-master-input').forEach(function (el) {
      const id = el.dataset.masterId;
      if (id) values[id] = el.value;
    });
    const hidden = document.getElementById('masterHiddenInputs');
    const ids = hidden
      ? Array.from(hidden.querySelectorAll('input[name="employee_ids"]')).map(function (i) { return i.value; })
      : [];
    const suggested = suggestedSalaryForMasters(ids);
    grid.innerHTML = '';
    ids.forEach(function (id) {
      const master = masters.find(function (m) { return String(m.id) === String(id); });
      if (!master) return;
      const label = document.createElement('label');
      label.className = 'salary-master-row';
      let val = values[id];
      if (val === undefined || val === '') {
        if (existing[id] !== undefined && existing[id] !== null && existing[id] !== '') {
          val = existing[id];
        } else if (suggested[id] !== undefined) {
          val = suggested[id];
        } else {
          val = '';
        }
      }
      const span = document.createElement('span');
      span.textContent = master.name;
      const input = document.createElement('input');
      input.name = 'salary_' + id;
      input.type = 'number';
      input.step = '0.01';
      input.min = '0';
      input.className = 'salary-master-input';
      input.dataset.masterId = id;
      input.placeholder = 'ЗП ₽';
      if (val !== '' && val !== null && val !== undefined) input.value = val;
      label.appendChild(span);
      label.appendChild(input);
      grid.appendChild(label);
    });
    const multi = ids.length > 1;
    const hint = document.getElementById('salaryMultiHint');
    const note = document.getElementById('salaryMultiNote');
    const totalWrap = document.getElementById('salaryTotalWrap');
    if (hint) hint.hidden = !multi;
    if (note) note.hidden = !multi;
    if (totalWrap) totalWrap.hidden = !multi;
    recalcSalaryTotal();
    grid.querySelectorAll('.salary-master-input').forEach(function (el) {
      el.addEventListener('input', function () {
        el.dataset.manual = '1';
        recalcSalaryTotal();
        if (typeof window.BS_onSalaryChanged === 'function') window.BS_onSalaryChanged();
      });
    });
    if (typeof window.BS_onSalaryChanged === 'function') window.BS_onSalaryChanged();
  }

  function refreshSuggestedSalariesFromPrice() {
    const grid = document.getElementById('salaryMasterGrid');
    if (!grid) return;
    const hidden = document.getElementById('masterHiddenInputs');
    const ids = hidden
      ? Array.from(hidden.querySelectorAll('input[name="employee_ids"]')).map(function (i) { return i.value; })
      : [];
    const suggested = suggestedSalaryForMasters(ids);
    grid.querySelectorAll('.salary-master-input').forEach(function (el) {
      if (el.dataset.manual === '1') return;
      const id = el.dataset.masterId;
      if (suggested[id] !== undefined) el.value = suggested[id];
    });
    recalcSalaryTotal();
    if (typeof window.BS_onSalaryChanged === 'function') window.BS_onSalaryChanged();
  }

  function initMasterPicker() {
    const picker = document.getElementById('masterPicker');
    if (!picker) return;
    const masters = window.BS_MASTERS || [];
    const initial = (window.BS_INITIAL_MASTERS || []).map(String);
    const select = document.getElementById('masterSelect');
    const addBtn = document.getElementById('addMasterBtn');
    const chips = document.getElementById('masterChips');
    const cardGrid = document.getElementById('masterCardGrid');
    const hidden = document.getElementById('masterHiddenInputs');
    const emptyHint = document.getElementById('masterEmptyHint');
    const formId = picker.dataset.formId;
    const form = formId ? document.getElementById(formId) : picker.closest('form');
    const selected = new Set();
    const uiCards = picker.dataset.ui === 'cards' && cardGrid;
    const tones = ['#2979ff', '#00b368', '#ff9500', '#9b51e0', '#ff3b30'];

    if (select && !uiCards) {
      masters.forEach(function (m) {
        const opt = document.createElement('option');
        opt.value = String(m.id);
        opt.textContent = m.name;
        select.appendChild(opt);
      });
    }

    function syncEmptyHint() {
      if (emptyHint) emptyHint.hidden = selected.size > 0;
    }

    function showMasterError(show) {
      picker.classList.toggle('field-error', !!show);
      const hint = picker.querySelector('.master-required-hint');
      if (hint) hint.hidden = !show;
    }

    function syncHidden() {
      if (!hidden) return;
      hidden.innerHTML = '';
      selected.forEach(function (sid) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'employee_ids';
        input.value = sid;
        input.dataset.id = sid;
        hidden.appendChild(input);
      });
    }

    function firstName(name) {
      return ((name || '').trim().split(/\s+/)[0]) || 'Мастер';
    }

    function initials(name) {
      const parts = (name || '').trim().split(/\s+/).filter(Boolean);
      if (!parts.length) return '?';
      if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
      return (parts[0].slice(0, 1) + parts[1].slice(0, 1)).toUpperCase();
    }

    function renderCards() {
      if (!cardGrid) return;
      cardGrid.innerHTML = '';
      masters.forEach(function (m, idx) {
        const sid = String(m.id);
        const on = selected.has(sid);
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'jr-mcard' + (on ? ' on' : '');
        card.dataset.id = sid;
        const av = document.createElement('div');
        av.className = 'jr-mav';
        av.style.background = tones[idx % tones.length];
        av.textContent = initials(m.name);
        const b = document.createElement('b');
        b.textContent = firstName(m.name);
        const small = document.createElement('small');
        small.textContent = on ? 'выбран' : 'свободен';
        card.appendChild(av);
        card.appendChild(b);
        card.appendChild(small);
        card.addEventListener('click', function () {
          if (selected.has(sid)) {
            selected.delete(sid);
          } else {
            // journal sheet: one primary master by default (tap another replaces)
            selected.clear();
            selected.add(sid);
          }
          renderCards();
          syncHidden();
          syncEmptyHint();
          showMasterError(false);
          syncSalaryMasterGrid();
        });
        cardGrid.appendChild(card);
      });
    }

    function addMaster(id) {
      const sid = String(id);
      if (!sid || selected.has(sid)) {
        if (uiCards) {
          renderCards();
          syncHidden();
        }
        return;
      }
      const master = masters.find(function (m) { return String(m.id) === sid; });
      if (!master) return;
      if (uiCards) {
        selected.clear();
        selected.add(sid);
        renderCards();
        syncHidden();
        syncEmptyHint();
        showMasterError(false);
        syncSalaryMasterGrid();
        return;
      }
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
        syncSalaryMasterGrid();
      });
      chips.appendChild(chip);
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'employee_ids';
      input.value = sid;
      input.dataset.id = sid;
      hidden.appendChild(input);
      if (select) select.value = '';
      syncEmptyHint();
      showMasterError(false);
      syncSalaryMasterGrid();
    }

    function clearMasters() {
      selected.clear();
      if (uiCards) {
        renderCards();
        syncHidden();
      } else {
        if (chips) chips.innerHTML = '';
        if (hidden) hidden.innerHTML = '';
      }
      syncEmptyHint();
      syncSalaryMasterGrid();
    }

    window.BS_setAppointmentMasters = function (ids) {
      clearMasters();
      (ids || []).forEach(function (id) {
        if (id && String(id) !== '0') addMaster(id);
      });
    };

    if (uiCards) {
      initial.forEach(function (id) { if (id) selected.add(String(id)); });
      // keep only first for card UI if multiple initial
      if (selected.size > 1) {
        const first = initial.find(Boolean);
        selected.clear();
        if (first) selected.add(String(first));
      }
      renderCards();
      syncHidden();
      syncSalaryMasterGrid();
    } else {
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
      syncSalaryMasterGrid();
    }

    if (form) {
      form.addEventListener('submit', function (e) {
        if (window.BS_CLOSE_SKIP_MASTER_REQUIRED) return;
        if (!selected.size) {
          e.preventDefault();
          showMasterError(true);
          picker.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const msg = picker.querySelector('.master-required-hint');
          if (msg) {
            msg.hidden = false;
            msg.textContent = 'Укажите хотя бы одного мастера';
          }
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
      initServicePicker();
      const priceForSalary = document.querySelector('input[name="price"], #closePriceInput');
      if (priceForSalary) {
        priceForSalary.addEventListener('input', refreshSuggestedSalariesFromPrice);
        priceForSalary.addEventListener('change', refreshSuggestedSalariesFromPrice);
      }
      pollIncomingCall();
      setInterval(pollIncomingCall, 2500);
      initPullToRefresh();
      const tabs = document.getElementById('mobileTabs');
      if (tabs) {
        const active = tabs.querySelector('a.active');
        if (active) active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
      }
    });
  }

  function initPullToRefresh() {
    if (!isMobile()) return;
    const scroller = document.querySelector('main.main.scrollable');
    if (!scroller || scroller.dataset.ptrInit === '1') return;
    scroller.dataset.ptrInit = '1';
    const ptr = document.createElement('div');
    ptr.className = 'bs-ptr';
    ptr.innerHTML = '<div class="bs-ptr-pill">Обновить</div>';
    scroller.prepend(ptr);
    const pill = ptr.querySelector('.bs-ptr-pill');
    let startY = 0;
    let pulling = false;
    let armed = false;
    const THRESHOLD = 72;

    function reset() {
      pulling = false;
      armed = false;
      ptr.classList.remove('is-visible', 'is-ready');
      ptr.style.transform = '';
      if (pill) pill.textContent = 'Обновить';
    }

    scroller.addEventListener('touchstart', function (e) {
      if (document.body.classList.contains('jr-sheet-open')) return;
      if (scroller.scrollTop > 2) return;
      if (e.touches.length !== 1) return;
      startY = e.touches[0].clientY;
      pulling = true;
      armed = false;
    }, { passive: true });

    scroller.addEventListener('touchmove', function (e) {
      if (document.body.classList.contains('jr-sheet-open')) { reset(); return; }
      if (!pulling) return;
      if (scroller.scrollTop > 2) { reset(); return; }
      const dy = e.touches[0].clientY - startY;
      if (dy < 8) {
        ptr.classList.remove('is-visible', 'is-ready');
        return;
      }
      ptr.classList.add('is-visible');
      const pull = Math.min(dy, 110);
      ptr.style.transform = 'translateY(' + (pull * 0.35) + 'px)';
      if (dy >= THRESHOLD) {
        armed = true;
        ptr.classList.add('is-ready');
        if (pill) pill.textContent = 'Отпустите';
      } else {
        armed = false;
        ptr.classList.remove('is-ready');
        if (pill) pill.textContent = 'Потяните';
      }
    }, { passive: true });

    scroller.addEventListener('touchend', function () {
      if (!pulling) return;
      if (armed) {
        if (pill) pill.textContent = 'Обновляю…';
        setTimeout(function () { location.reload(); }, 120);
        return;
      }
      reset();
    });

    scroller.addEventListener('touchcancel', reset);
  }
})();
