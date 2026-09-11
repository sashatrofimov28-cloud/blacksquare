(function () {
  function copyText(text) {
    text = String(text || '');
    if (!text) return Promise.resolve(false);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () {
        return fallbackCopy(text);
      });
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function fallbackCopy(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return !!ok;
    } catch (e) {
      return false;
    }
  }

  function showHint(el, ms) {
    if (!el) return;
    el.hidden = false;
    el.removeAttribute('hidden');
    el.classList.add('is-visible');
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(function () {
      el.hidden = true;
      el.setAttribute('hidden', '');
      el.classList.remove('is-visible');
    }, ms || 5000);
  }

  function openTelegram(phoneDigits, href) {
    var digits = String(phoneDigits || '').replace(/\D+/g, '');
    var deep = href || (digits ? ('tg://resolve?phone=' + digits) : '');
    if (!deep) return;
    // Пробуем приложение; если не открылось — оставляем пользователя в TG (или копируем номер)
    window.location.href = deep;
  }

  function openMax(phoneDigits, href) {
    var digits = String(phoneDigits || '').replace(/\D+/g, '');
    var phone = digits ? ('+' + digits) : '';
    return copyText(phone).then(function () {
      // Прямого deep-link «чат по номеру» у MAX нет — копируем номер и открываем приложение.
      var url = href || 'https://max.ru/';
      setTimeout(function () {
        window.location.href = url;
      }, 60);
      return true;
    });
  }

  function bind() {
    document.querySelectorAll('a.js-msg-telegram, a[data-msg="telegram"]').forEach(function (a) {
      if (a.dataset.msgBound === '1') return;
      a.dataset.msgBound = '1';
      a.addEventListener('click', function (e) {
        var digits = a.getAttribute('data-digits') || '';
        var href = a.getAttribute('href') || '';
        // Если это tg:// — даём браузеру/приложению открыть напрямую
        if (href.indexOf('tg://') === 0) return;
        e.preventDefault();
        openTelegram(digits, href);
      });
    });

    document.querySelectorAll('a.js-msg-max, a[data-msg="max"]').forEach(function (a) {
      if (a.dataset.msgBound === '1') return;
      a.dataset.msgBound = '1';
      a.addEventListener('click', function (e) {
        e.preventDefault();
        var digits = a.getAttribute('data-digits') || (a.getAttribute('data-phone') || '').replace(/\D+/g, '');
        var href = a.getAttribute('href') || 'https://max.ru/';
        var hint = document.getElementById(a.getAttribute('data-hint') || 'clientMsgHint')
          || a.parentElement && a.parentElement.querySelector('.client-msg-hint, .crm-z-msg-hint');
        openMax(digits, href).then(function () {
          showHint(hint, 5000);
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

  window.BS_copyText = copyText;
  window.BS_openTelegram = openTelegram;
  window.BS_openMax = openMax;
})();
