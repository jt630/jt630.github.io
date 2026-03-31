(function () {
  'use strict';

  var authSel   = document.getElementById('api-filter-auth');
  var statusSel = document.getElementById('api-filter-status');
  var searchInp = document.getElementById('api-filter-search');
  var clearBtn  = document.getElementById('api-filter-clear');

  if (!authSel) return; // page not loaded

  function applyFilters() {
    var auth   = authSel.value;
    var status = statusSel.value;
    var search = searchInp.value.trim().toLowerCase();

    document.querySelectorAll('.api-cluster').forEach(function (cluster) {
      var cards = cluster.querySelectorAll('.api-card');
      var visible = 0;

      cards.forEach(function (card) {
        var matchAuth   = !auth   || card.dataset.auth   === auth;
        var matchStatus = !status || card.dataset.status === status;
        var nameEl = card.querySelector('.api-card-name');
        var matchSearch = !search || (nameEl && nameEl.textContent.toLowerCase().indexOf(search) !== -1);

        if (matchAuth && matchStatus && matchSearch) {
          card.style.display = '';
          visible++;
        } else {
          card.style.display = 'none';
        }
      });

      if (visible === 0) {
        cluster.open = false;
        cluster.classList.add('api-cluster--empty');
      } else {
        cluster.classList.remove('api-cluster--empty');
      }
    });

    saveHash();
  }

  function saveHash() {
    var parts = [];
    if (authSel.value)        parts.push('auth='   + encodeURIComponent(authSel.value));
    if (statusSel.value)      parts.push('status=' + encodeURIComponent(statusSel.value));
    if (searchInp.value.trim()) parts.push('search=' + encodeURIComponent(searchInp.value.trim()));
    history.replaceState(null, '', parts.length ? '#' + parts.join('&') : location.pathname);
  }

  function loadHash() {
    var hash = location.hash.replace(/^#/, '');
    if (!hash) return;
    hash.split('&').forEach(function (pair) {
      var kv = pair.split('=');
      var key = decodeURIComponent(kv[0]);
      var val = decodeURIComponent(kv[1] || '');
      if (key === 'auth')   authSel.value   = val;
      if (key === 'status') statusSel.value = val;
      if (key === 'search') searchInp.value = val;
    });
    applyFilters();
  }

  function clearFilters() {
    authSel.value   = '';
    statusSel.value = '';
    searchInp.value = '';
    document.querySelectorAll('.api-card').forEach(function (c) { c.style.display = ''; });
    document.querySelectorAll('.api-cluster').forEach(function (cl) {
      cl.classList.remove('api-cluster--empty');
    });
    history.replaceState(null, '', location.pathname);
  }

  authSel.addEventListener('change', applyFilters);
  statusSel.addEventListener('change', applyFilters);
  searchInp.addEventListener('input', applyFilters);
  clearBtn.addEventListener('click', clearFilters);

  loadHash();
}());
