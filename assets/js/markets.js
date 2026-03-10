// markets.js — FRED API live data for Almond Farm markets dashboard
// window.FRED_KEY is injected by the Hugo template from data/keys.yaml (gitignored).
// If the key is absent or any fetch fails, the static demo values remain visible.

(function () {
  'use strict';

  var KEY = window.FRED_KEY;
  if (!KEY) return;

  var BASE = 'https://api.stlouisfed.org/fred/series/observations';

  function url(id, limit) {
    return (
      BASE +
      '?series_id=' + id +
      '&api_key=' + KEY +
      '&file_type=json' +
      '&sort_order=desc' +
      '&limit=' + (limit || 1)
    );
  }

  function get(id, limit) {
    return fetch(url(id, limit))
      .then(function (r) { return r.json(); })
      .then(function (d) { return d.observations || []; })
      .catch(function () { return []; });
  }

  // Return parsed float from observation at index, or null if missing/"."
  function val(obs, index) {
    var o = obs[index || 0];
    if (!o || o.value === '.') return null;
    return parseFloat(o.value);
  }

  function fmt(n, dec) {
    if (n === null || n === undefined) return null;
    return n.toFixed(dec !== undefined ? dec : 2);
  }

  function set(id, text) {
    var el = document.getElementById(id);
    if (el && text !== null) {
      el.textContent = text;
      el.style.opacity = '1';
    }
  }

  function setClass(id, cls) {
    var el = document.getElementById(id);
    if (el) el.className = 'markets-value ' + cls;
  }

  // Dim all values to signal loading
  document.querySelectorAll('.markets-value').forEach(function (el) {
    el.style.opacity = '0.35';
  });

  // Fire all FRED requests concurrently — well within the 120 req/min limit
  Promise.all([
    get('FEDFUNDS'),           // 0  Fed Funds Rate
    get('DGS10'),              // 1  10Y Treasury
    get('DGS2'),               // 2  2Y Treasury
    get('T10Y2Y'),             // 3  Yield curve spread
    get('WALCL'),              // 4  Fed balance sheet (millions USD)
    get('M2SL'),               // 5  M2 money supply (billions USD)
    get('PCEPILFE', 13),       // 6  Core PCE — 13 obs for YoY
    get('CPIAUCSL', 13),       // 7  CPI — 13 obs for YoY
    get('CPILFESL', 13),       // 8  Core CPI — 13 obs for YoY
    get('UNRATE'),             // 9  Unemployment rate
    get('PAYEMS', 2),          // 10 Nonfarm payrolls (thousands) — 2 for MoM
    get('ICSA'),               // 11 Initial jobless claims (raw number)
    get('JTSJOL'),             // 12 JOLTS job openings (thousands)
    get('MORTGAGE30US'),       // 13 30Y fixed mortgage rate
    get('MORTGAGE15US'),       // 14 15Y fixed mortgage rate
    get('HOUST'),              // 15 Housing starts (thousands, annualized)
    get('EXHOSLUSM495S'),      // 16 Existing home sales (thousands, annualized)
    get('BAMLC0A4CBBB'),       // 17 BBB corporate spread
    get('BAMLH0A0HYM2'),       // 18 High yield spread
  ]).then(function (r) {

    // ── Fed & Rates ──────────────────────────────────
    var ff = val(r[0]);
    set('FEDFUNDS', ff !== null ? fmt(ff) + '%' : null);

    var y10 = val(r[1]);
    set('DGS10', y10 !== null ? fmt(y10) + '%' : null);

    var y2 = val(r[2]);
    set('DGS2', y2 !== null ? fmt(y2) + '%' : null);

    var curve = val(r[3]);
    if (curve !== null) {
      var sign = curve >= 0 ? '+' : '';
      var curveStr = sign + fmt(curve) + '%';
      var curveCls = curve >= 0 ? 'positive' : 'warn';
      set('T10Y2Y', curveStr);
      setClass('T10Y2Y', curveCls);
      set('T10Y2Y-credit', curveStr);
      setClass('T10Y2Y-credit', curveCls);
    }

    // WALCL: millions of USD → trillions
    var bs = val(r[4]);
    set('WALCL', bs !== null ? '$' + (bs / 1e6).toFixed(1) + 'T' : null);

    // M2SL: billions of USD → trillions
    var m2 = val(r[5]);
    set('M2SL', m2 !== null ? '$' + (m2 / 1e3).toFixed(1) + 'T' : null);

    // ── Inflation (YoY = (latest - 12mo ago) / 12mo ago × 100) ──────────
    function yoy(obs) {
      var latest = val(obs, 0);
      var prev   = val(obs, 12);
      if (latest === null || prev === null || prev === 0) return null;
      return ((latest - prev) / prev) * 100;
    }

    var pceYoy = yoy(r[6]);
    set('PCEPILFE', pceYoy !== null ? fmt(pceYoy, 1) + '% YoY' : null);

    var cpiYoy = yoy(r[7]);
    set('CPIAUCSL', cpiYoy !== null ? fmt(cpiYoy, 1) + '% YoY' : null);

    var coreCpiYoy = yoy(r[8]);
    set('CPILFESL', coreCpiYoy !== null ? fmt(coreCpiYoy, 1) + '% YoY' : null);

    // ── Labor ────────────────────────────────────────
    var ur = val(r[9]);
    set('UNRATE', ur !== null ? fmt(ur, 1) + '%' : null);

    // PAYEMS: MoM change in thousands of persons
    var p0 = val(r[10], 0), p1 = val(r[10], 1);
    if (p0 !== null && p1 !== null) {
      var diff = Math.round(p0 - p1);
      set('PAYEMS', (diff >= 0 ? '+' : '') + diff.toLocaleString() + 'k');
    }

    // ICSA: raw number (not thousands)
    var claims = val(r[11]);
    set('ICSA', claims !== null ? Math.round(claims / 1000) + 'k' : null);

    // JTSJOL: thousands → millions
    var jv = val(r[12]);
    set('JTSJOL', jv !== null ? (jv / 1000).toFixed(1) + 'M' : null);

    // ── Housing ──────────────────────────────────────
    var m30 = val(r[13]);
    set('MORTGAGE30US', m30 !== null ? fmt(m30) + '%' : null);

    var m15 = val(r[14]);
    set('MORTGAGE15US', m15 !== null ? fmt(m15) + '%' : null);

    // HOUST: thousands annualized → millions
    var hs = val(r[15]);
    set('HOUST', hs !== null ? (hs / 1000).toFixed(2) + 'M' : null);

    // EXHOSLUSM495S: thousands annualized → millions
    var eh = val(r[16]);
    set('EXHOSLUSM495S', eh !== null ? (eh / 1000).toFixed(2) + 'M' : null);

    // ── Credit ───────────────────────────────────────
    var bbbv = val(r[17]);
    set('BAMLC0A4CBBB', bbbv !== null ? fmt(bbbv) + '%' : null);

    var hyv = val(r[18]);
    set('BAMLH0A0HYM2', hyv !== null ? fmt(hyv) + '%' : null);

    // ── Update header badge + timestamp ──────────────
    var badge = document.querySelector('.markets-static-badge');
    if (badge) {
      badge.textContent = '● LIVE DATA';
      badge.style.color = '#00FF41';
      badge.style.borderColor = '#00FF41';
      badge.style.background = '#001400';
      badge.style.animation = 'none';
    }

    var now = new Date();
    var ts = document.getElementById('markets-last-updated');
    if (ts) {
      ts.textContent = 'fetched ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    var sub = document.getElementById('markets-source-footer');
    if (sub) sub.textContent = 'Source: FRED (St. Louis Fed) · updates on page load';

  }).catch(function () {
    // API error — restore full opacity so static values are readable
    document.querySelectorAll('.markets-value').forEach(function (el) {
      el.style.opacity = '1';
    });
  });
})();
