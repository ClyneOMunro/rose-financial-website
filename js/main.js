/* Rose Financial Management — site behavior. Vanilla JS, no dependencies. */
(function () {
  document.documentElement.classList.add('js');

  // Mobile navigation
  var toggle = document.querySelector('.nav-toggle');
  var links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // Scroll reveal (respects reduced motion via CSS)
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('in'); });
  }

  // Knowledge Base milestone filter
  var filterBar = document.querySelector('.kb-filter');
  if (filterBar) {
    var btns = filterBar.querySelectorAll('.kb-filter-btn');
    var cards = document.querySelectorAll('.kb-grid .kb-card');
    filterBar.addEventListener('click', function (e) {
      var btn = e.target.closest('.kb-filter-btn');
      if (!btn) return;
      var f = btn.getAttribute('data-filter');
      btns.forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      cards.forEach(function (c) {
        var cats = (c.getAttribute('data-cats') || '').split(/\s+/);
        var show = f === 'all' || cats.indexOf(f) !== -1;
        c.classList.toggle('is-filtered', !show);
      });
    });
  }

  // Loss-kit audience selector
  var audBar = document.querySelector('.aud-filter');
  if (audBar) {
    var audBtns = audBar.querySelectorAll('.aud-btn');
    var audItems = document.querySelectorAll('.article-list li[data-aud-cats]');
    var audNotes = audBar.querySelectorAll('.aud-note');
    audBar.addEventListener('click', function (e) {
      var btn = e.target.closest('.aud-btn');
      if (!btn) return;
      var f = btn.getAttribute('data-aud');
      audBtns.forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      audItems.forEach(function (li) {
        var cats = (li.getAttribute('data-aud-cats') || '').split(/\s+/);
        var show = f === 'all' || cats.indexOf(f) !== -1;
        li.classList.toggle('is-aud-filtered', !show);
      });
      audNotes.forEach(function (n) {
        n.hidden = n.getAttribute('data-aud-note') !== f;
      });
    });
  }

  // Footer year
  var yr = document.querySelector('[data-year]');
  if (yr) yr.textContent = new Date().getFullYear();
})();
