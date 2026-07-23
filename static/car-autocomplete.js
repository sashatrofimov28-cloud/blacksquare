(function () {
  var catalog = null;
  var catalogPromise = null;

  function loadCatalog() {
    if (catalog) return Promise.resolve(catalog);
    if (catalogPromise) return catalogPromise;
    catalogPromise = fetch('/static/data/car-catalog.json?v=3')
      .then(function (r) { return r.json(); })
      .then(function (d) { catalog = d; return d; })
      .catch(function () { catalog = { brands: [] }; return catalog; });
    return catalogPromise;
  }

  function withPhoto(item) {
    var photo = '';
    if (window.BS_carPhotoUrl && item.kind !== 'brand') {
      photo = window.BS_carPhotoUrl(item.value, item.hint || '', 160);
    } else if (window.BS_carPhotoUrl && item.kind === 'brand') {
      photo = window.BS_carPhotoUrl(item.value, '', 160);
    }
    item.photo = photo;
    return item;
  }

  function norm(s) {
    return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();
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

  function aliasHit(query, alias) {
    var q = norm(query);
    var a = norm(alias);
    if (!q || !a) return 0;
    if (a === q) return 100;
    if (a.indexOf(q) === 0) return 70 + Math.min(q.length, 20);
    if (q.indexOf(a) === 0 && a.length >= 3) return 55;
    if (a.indexOf(q) > -1) return 35;
    var qTokens = q.split(/\s+/).filter(Boolean);
    var aTokens = a.split(/\s+/).filter(Boolean);
    if (!qTokens.length || !aTokens.length) return 0;
    var hit = 0;
    qTokens.forEach(function (qt) {
      var best = 0;
      aTokens.forEach(function (at) {
        if (at === qt) best = Math.max(best, 30);
        else if (at.indexOf(qt) === 0 || (qt.indexOf(at) === 0 && at.length >= 3)) best = Math.max(best, 18);
        else if (at.indexOf(qt) > -1 || qt.indexOf(at) > -1) best = Math.max(best, 10);
      });
      hit += best;
    });
    return hit >= 18 ? hit : 0;
  }

  function bestAlias(query, aliases) {
    var best = 0;
    (aliases || []).forEach(function (a) {
      best = Math.max(best, aliasHit(query, a));
    });
    return best;
  }

  function resolveLocal(raw) {
    var q = norm(raw);
    var tokens = q.split(/\s+/).filter(Boolean);
    if (!tokens.length || !catalog) return '';
    var bestModel = null;
    var bestBrand = null;
    (catalog.brands || []).forEach(function (b) {
      var brand = b.name;
      var brandAliases = [brand].concat(b.aliases || []);
      var bWhole = bestAlias(q, brandAliases);
      var bFirst = bestAlias(tokens[0], brandAliases);
      var brandScore = Math.max(bWhole, bFirst);
      if (brandScore >= 55 && (!bestBrand || brandScore > bestBrand.score)) {
        bestBrand = { score: brandScore, name: brand };
      }
      var remainder = '';
      if (bFirst >= 55) remainder = tokens.slice(1).join(' ');
      else if (bWhole >= 55 && tokens.length === 1) remainder = '';
      (b.models || []).forEach(function (model) {
        var mname = modelName(model);
        if (!mname) return;
        var mAliases = [mname].concat(modelAliases(model));
        var label = brand + ' ' + mname;
        var mOnly = bestAlias(q, mAliases);
        var mRem = remainder ? bestAlias(remainder, mAliases) : 0;
        var fullAliases = [];
        brandAliases.forEach(function (ba) {
          mAliases.forEach(function (ma) { fullAliases.push((ba + ' ' + ma).trim()); });
        });
        var fullScore = bestAlias(q, fullAliases);
        if (!remainder && brandScore >= 55) fullScore = 0;
        var score = 0;
        if (remainder && mRem >= 40 && brandScore >= 40) score = Math.max(score, brandScore + mRem + 40);
        if (mOnly >= 70) score = Math.max(score, mOnly + (brandScore >= 40 ? 20 : 0));
        if (fullScore >= 80) score = Math.max(score, fullScore + 15);
        if (score < 70) return;
        if (!bestModel || score > bestModel.score) bestModel = { score: score, label: label };
      });
    });
    if (bestModel) return bestModel.label;
    if (bestBrand) return bestBrand.name;
    return '';
  }

  function filterCatalog(q, limit) {
    var nq = norm(q);
    if (!nq) return [];
    var tokens = nq.split(/\s+/).filter(Boolean);
    var scored = [];
    (catalog.brands || []).forEach(function (b) {
      var brand = b.name;
      var meta = brandMeta(b);
      var brandAliases = [brand].concat(b.aliases || []);
      var first = tokens[0] || nq;
      var brandScore = Math.max(bestAlias(first, brandAliases), bestAlias(nq, brandAliases));
      if (brandScore >= 40 && tokens.length <= 1) {
        scored.push({
          score: brandScore - 5,
          item: withPhoto({ label: brand, value: brand, kind: 'brand', color: meta.color, initials: meta.initials, hint: '' })
        });
      }
      (b.models || []).forEach(function (model) {
        var mname = modelName(model);
        if (!mname) return;
        var aliases = modelAliases(model);
        var mAliases = [mname].concat(aliases);
        var full = brand + ' ' + mname;
        var fullAliases = [];
        brandAliases.forEach(function (ba) {
          mAliases.forEach(function (ma) { fullAliases.push((ba + ' ' + ma).trim()); });
        });
        var fullScore = bestAlias(nq, fullAliases);
        var modelScore = bestAlias(nq, mAliases);
        var combo = 0;
        if (tokens.length >= 2) {
          var pairs = [
            [tokens.slice(0, -1).join(' '), tokens[tokens.length - 1]],
            [tokens[0], tokens.slice(1).join(' ')]
          ];
          pairs.forEach(function (p) {
            var bSc = bestAlias(p[0], brandAliases);
            var mSc = bestAlias(p[1], mAliases);
            if (bSc && mSc) combo = Math.max(combo, bSc + mSc + 30);
          });
        }
        var score = Math.max(fullScore, combo, modelScore + (brandScore ? 15 : 0));
        if (brandScore >= 40 && tokens.length === 1 && score < brandScore) score = Math.max(score, brandScore - 8);
        if (score < 18) return;
        var matched = aliases.find(function (a) {
          var na = norm(a);
          return na === nq || na.indexOf(nq) === 0;
        });
        var hint = matched || '';
        var label = full + (hint && norm(full).indexOf(norm(hint)) < 0 ? ' · ' + hint : '');
        scored.push({
          score: score,
          item: withPhoto({
            label: label,
            value: full,
            kind: 'model',
            hint: hint,
            color: meta.color,
            initials: meta.initials
          })
        });
      });
    });
    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return String(a.item.value).localeCompare(String(b.item.value));
    });
    var out = [];
    var seen = {};
    scored.forEach(function (row) {
      var v = row.item.value;
      if (seen[v]) return;
      seen[v] = 1;
      out.push(row.item);
    });
    return out.slice(0, limit);
  }

  function fetchDb(q) {
    return fetch('/api/cars/suggest?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (d) { return d.items || []; })
      .catch(function () { return []; });
  }

  function resolveRemote(q) {
    return fetch('/api/cars/resolve?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (d) { return (d && d.value) || ''; })
      .catch(function () { return ''; });
  }

  function mergeItems(a, b, limit) {
    var seen = {};
    var out = [];
    a.concat(b).forEach(function (item) {
      var v = item.value || item.label;
      if (!v || seen[v]) return;
      seen[v] = 1;
      out.push(withPhoto({
        label: item.label || v,
        value: v,
        kind: item.kind || 'history',
        hint: item.hint || '',
        color: item.color || '#666',
        initials: item.initials || '·'
      }));
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
    if (item.photo) {
      t.classList.add('has-photo');
      var img = document.createElement('img');
      img.src = item.photo;
      img.alt = '';
      img.loading = 'lazy';
      img.onerror = function () {
        t.classList.remove('has-photo');
        img.remove();
        t.style.background = item.color || '#555';
      };
      t.appendChild(img);
      return t;
    }
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
        selectItem(wrap, item);
      });
      list.appendChild(btn);
    });
    openList(wrap);
  }

  function selectItem(wrap, itemOrValue) {
    var item = typeof itemOrValue === 'string'
      ? { value: itemOrValue, label: itemOrValue, hint: '', photo: window.BS_carPhotoUrl ? window.BS_carPhotoUrl(itemOrValue, '', 400) : '' }
      : itemOrValue;
    var input = wrap.querySelector('input');
    input.value = item.value;
    input.dataset.carHint = item.hint || '';
    input.dataset.carPhoto = item.photo || (window.BS_carPhotoUrl ? window.BS_carPhotoUrl(item.value, item.hint || '', 400) : '');
    input.dataset.carResolved = '1';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new CustomEvent('bs:car-selected', {
      bubbles: true,
      detail: {
        value: item.value,
        label: item.label || item.value,
        hint: item.hint || '',
        photo: input.dataset.carPhoto,
        photoLarge: window.BS_carPhotoUrlLarge ? window.BS_carPhotoUrlLarge(item.value, item.hint || '') : input.dataset.carPhoto
      }
    }));
    closeList(wrap);
  }

  function resolveInput(wrap, input) {
    var q = input.value.trim();
    if (!q || input.dataset.carResolved === '1') return;
    loadCatalog().then(function () {
      var local = resolveLocal(q);
      var apply = function (value) {
        if (!value || value === q) return;
        selectItem(wrap, { value: value, label: value, hint: '', kind: 'model' });
      };
      if (local && local !== q) {
        apply(local);
        return;
      }
      resolveRemote(q).then(function (remote) {
        if (remote && remote !== q) apply(remote);
      });
    });
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
      input.dataset.carResolved = '0';
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
        selectItem(wrap, items[activeIdx]);
      } else if (e.key === 'Escape') {
        closeList(wrap);
      }
    });

    input.addEventListener('blur', function () {
      setTimeout(function () {
        closeList(wrap);
        resolveInput(wrap, input);
      }, 150);
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
