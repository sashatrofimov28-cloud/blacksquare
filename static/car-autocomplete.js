(function () {
  var catalog = null;
  var catalogPromise = null;

  function loadCatalog() {
    if (catalog) return Promise.resolve(catalog);
    if (catalogPromise) return catalogPromise;
    catalogPromise = fetch('/static/data/car-catalog.json?v=1')
      .then(function (r) { return r.json(); })
      .then(function (d) { catalog = d; return d; })
      .catch(function () { catalog = { brands: [] }; return catalog; });
    return catalogPromise;
  }

  function norm(s) {
    return (s || '').toLowerCase().replace(/ё/g, 'е').trim();
  }

  function filterCatalog(q, limit) {
    var nq = norm(q);
    if (!nq) return [];
    var out = [];
    var seen = {};
    (catalog.brands || []).forEach(function (b) {
      var brand = b.name;
      var nb = norm(brand);
      var names = [brand].concat(b.aliases || []);
      var brandHit = names.some(function (n) {
        var nn = norm(n);
        return nn.indexOf(nq) === 0 || nn.indexOf(nq) > -1;
      });
      if (brandHit && !seen[brand]) {
        out.push({ label: brand, value: brand, kind: 'brand' });
        seen[brand] = 1;
      }
      (b.models || []).forEach(function (model) {
        var full = brand + ' ' + model;
        var nf = norm(full);
        var nm = norm(model);
        if (nf.indexOf(nq) === 0 || nm.indexOf(nq) === 0 || nf.indexOf(nq) > -1) {
          if (!seen[full]) {
            out.push({ label: full, value: full, kind: 'model' });
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
      out.push({ label: item.label || v, value: v, kind: item.kind || 'history' });
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
      btn.textContent = item.label;
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
