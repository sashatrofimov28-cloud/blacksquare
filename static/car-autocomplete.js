(function () {
  var catalog = null;
  var catalogPromise = null;

  function loadCatalog() {
    if (catalog) return Promise.resolve(catalog);
    if (catalogPromise) return catalogPromise;
    catalogPromise = fetch('/static/data/car-catalog.json?v=2')
      .then(function (r) { return r.json(); })
      .then(function (d) { catalog = d; return d; })
      .catch(function () { catalog = { brands: [] }; return catalog; });
    return catalogPromise;
  }

  function norm(s) {
    return (s || '').toLowerCase().replace(/ё/g, 'е').trim();
  }

  function modelName(model) {
    return typeof model === 'object' && model ? (model.name || '') : String(model || '');
  }

  function modelAliases(model) {
    return (typeof model === 'object' && model && model.aliases) ? model.aliases : [];
  }

  function brandMeta(b) {
    return {
      color: b.color || '#555',
      initials: (b.name || '?').split(/\s+/).slice(0, 2).map(function (w) { return w.charAt(0); }).join('').toUpperCase()
    };
  }

  function filterCatalog(q, limit) {
    var nq = norm(q);
    if (!nq) return [];
    var out = [];
    var seen = {};
    (catalog.brands || []).forEach(function (b) {
      var brand = b.name;
      var meta = brandMeta(b);
      var names = [brand].concat(b.aliases || []);
      var brandHit = names.some(function (n) {
        var nn = norm(n);
        return nn.indexOf(nq) === 0 || nn.indexOf(nq) > -1;
      });
      if (brandHit && !seen[brand]) {
        out.push({ label: brand, value: brand, kind: 'brand', color: meta.color, initials: meta.initials, hint: '' });
        seen[brand] = 1;
      }
      (b.models || []).forEach(function (model) {
        var mname = modelName(model);
        if (!mname) return;
        var aliases = modelAliases(model);
        var full = brand + ' ' + mname;
        var nf = norm(full);
        var nm = norm(mname);
        var aliasHit = aliases.some(function (a) {
          var na = norm(a);
          return na === nq || na.indexOf(nq) === 0 || nq.indexOf(na) === 0 || na.indexOf(nq) > -1;
        });
        if (nf.indexOf(nq) === 0 || nm.indexOf(nq) === 0 || nf.indexOf(nq) > -1 || aliasHit) {
          if (!seen[full]) {
            var matched = aliases.find(function (a) {
              var na = norm(a);
              return na === nq || na.indexOf(nq) === 0;
            });
            var hint = matched || (aliases[0] || '');
            var label = full + (hint && nf.indexOf(norm(hint)) < 0 ? ' · ' + hint : '');
            out.push({
              label: label,
              value: full,
              kind: 'model',
              hint: hint,
              color: meta.color,
              initials: meta.initials
            });
            seen[full] = 1;
          }
        }
      });
    });
    return out.slice(0, limit);
  }

  function fetchDb(q) {
    return fetch('/api/cars/suggest?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (d) { return d.items || []; })
      .catch(function () { return []; });
  }

  function mergeItems(a, b, limit) {
    var seen = {};
    var out = [];
    a.concat(b).forEach(function (item) {
      var v = item.value || item.label;
      if (!v || seen[v]) return;
      seen[v] = 1;
      out.push({
        label: item.label || v,
        value: v,
        kind: item.kind || 'history',
        hint: item.hint || '',
        color: item.color || '#666',
        initials: item.initials || '🚗'
      });
    });
    return out.slice(0, limit);
  }

  function ensureWrap(input) {
    var wrap = input.closest('.car-ac-wrap');
    if (wrap) return wrap;
    wrap = document.createElement('div');
    wrap.className = 'car-ac-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var list = document.createElement('div');
    list.className = 'car-ac-list';
    list.hidden = true;
    wrap.appendChild(list);
    return wrap;
  }

  function closeList(wrap) {
    var list = wrap.querySelector('.car-ac-list');
    if (list) list.hidden = true;
    wrap.dataset.open = '0';
  }

  function openList(wrap) {
    var list = wrap.querySelector('.car-ac-list');
    if (list && list.children.length) {
      list.hidden = false;
      wrap.dataset.open = '1';
    }
  }

  function thumbEl(item) {
    var t = document.createElement('span');
    t.className = 'car-ac-thumb';
    t.style.background = item.color || '#555';
    t.textContent = item.initials || '·';
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 48 28');
    svg.setAttribute('class', 'car-ac-sil');
    svg.innerHTML = '<path fill="rgba(255,255,255,.92)" d="M8 20h32l-2-7c-1-3-3-5-6-5H16c-3 0-5 2-6 5l-2 7zm6-3a2.5 2.5 0 110 5 2.5 2.5 0 010-5zm20 0a2.5 2.5 0 110 5 2.5 2.5 0 010-5z"/>';
    t.appendChild(svg);
    return t;
  }

  function renderList(wrap, items, activeIdx) {
    var list = wrap.querySelector('.car-ac-list');
    list.innerHTML = '';
    if (!items.length) {
      list.hidden = true;
      wrap.dataset.open = '0';
      return;
    }
    items.forEach(function (item, idx) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'car-ac-item' + (idx === activeIdx ? ' is-active' : '');
      btn.appendChild(thumbEl(item));
      var text = document.createElement('span');
      text.className = 'car-ac-text';
      var main = document.createElement('b');
      main.textContent = item.value || item.label;
      text.appendChild(main);
      if (item.hint && String(item.label).indexOf(item.hint) >= 0) {
        var sub = document.createElement('small');
        sub.textContent = item.hint;
        text.appendChild(sub);
      } else if (item.kind === 'history') {
        var sub2 = document.createElement('small');
        sub2.textContent = 'из ваших записей';
        text.appendChild(sub2);
      }
      btn.appendChild(text);
      btn.dataset.value = item.value;
      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        selectItem(wrap, item.value);
      });
      list.appendChild(btn);
    });
    openList(wrap);
  }

  function selectItem(wrap, value) {
    var input = wrap.querySelector('input');
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    closeList(wrap);
  }

  function initCarAutocomplete(input) {
    if (!input || input.dataset.carAcInit === '1') return;
    input.dataset.carAcInit = '1';
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('spellcheck', 'false');
    var wrap = ensureWrap(input);
    var timer = null;
    var items = [];
    var activeIdx = -1;

    function runSuggest() {
      var q = input.value.trim();
      if (q.length < 1) {
        items = [];
        closeList(wrap);
        return;
      }
      loadCatalog().then(function () {
        var local = filterCatalog(q, 10);
        return fetchDb(q).then(function (db) {
          items = mergeItems(db, local, 12);
          activeIdx = -1;
          renderList(wrap, items, activeIdx);
        });
      });
    }

    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(runSuggest, 120);
    });

    input.addEventListener('focus', function () {
      if (input.value.trim().length >= 1) runSuggest();
    });

    input.addEventListener('keydown', function (e) {
      if (!items.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
        renderList(wrap, items, activeIdx);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
        renderList(wrap, items, activeIdx);
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        selectItem(wrap, items[activeIdx].value);
      } else if (e.key === 'Escape') {
        closeList(wrap);
      }
    });

    input.addEventListener('blur', function () {
      setTimeout(function () { closeList(wrap); }, 150);
    });
  }

  function boot() {
    document.querySelectorAll('input.js-car-ac, input[data-car-ac]').forEach(initCarAutocomplete);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.BS_initCarAutocomplete = initCarAutocomplete;
})();
