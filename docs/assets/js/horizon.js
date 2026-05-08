(function () {
  'use strict';

  /** Replace ⭐️ N/10 with a colored badge in h2, h3, and li elements */
  function processScoreBadges() {
    var scoreRe = /⭐️\s*(\d+(?:\.\d+)?)\/10/;
    var targets = document.querySelectorAll('.main-content h2, .main-content h3, .main-content li');
    targets.forEach(function (el) {
      var m = el.innerHTML.match(scoreRe);
      if (!m) return;
      var score = parseFloat(m[1]);
      var tier;
      if (score >= 9) tier = 'high';
      else if (score >= 7) tier = 'good';
      else if (score >= 5) tier = 'mid';
      else tier = 'low';
      el.innerHTML = el.innerHTML.replace(
        scoreRe,
        '<span class="score-badge" data-tier="' + tier + '">' + m[1] + '</span>'
      );
    });
  }

  /** Add semantic classes to tag lines, source lines, and background paragraphs */
  function markSemanticElements() {
    var paragraphs = document.querySelectorAll('.main-content p');
    paragraphs.forEach(function (p) {
      var text = p.textContent.trim();

      // Tag line: starts with Tags, 标签, or 태그 (bold prefix rendered by Markdown)
      if (/^(Tags|标签|태그)\s*:/.test(text)) {
        p.classList.add('tag-line');
        return;
      }

      // Source line: pattern like "source · site · date"
      if (/^(rss|reddit|github|hackernews|hn|telegram|youtube)\s*·/i.test(text)) {
        p.classList.add('source-line');
        return;
      }
    });
  }

  /** Add source-domain favicons before post links for visual scanning */
  function addPostFavicons() {
    function hostFromUrl(url) {
      try {
        var host = new URL(url, window.location.href).hostname.toLowerCase();
        return host.replace(/^www\./, '');
      } catch (e) {
        return '';
      }
    }

    function faviconFor(host) {
      return 'https://www.google.com/s2/favicons?domain=' + encodeURIComponent(host) + '&sz=32';
    }

    function makeIcon(host) {
      var img = document.createElement('img');
      img.className = 'post-favicon';
      img.src = faviconFor(host);
      img.alt = host + ' favicon';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      return img;
    }

    function sourceHostFromHeading(heading) {
      var cursor = heading.nextElementSibling;
      while (cursor) {
        if (cursor.matches && cursor.matches('h2')) break;
        if (cursor.matches && cursor.matches('p')) {
          var text = cursor.textContent.trim();
          if (/^hackernews\s*·/i.test(text)) return 'news.ycombinator.com';
          if (/^github\s*·/i.test(text)) return 'github.com';
          if (/^reddit\s*·/i.test(text)) return 'reddit.com';
          if (/^telegram\s*·/i.test(text)) return 't.me';
          if (/^twitter\s*·/i.test(text)) return 'x.com';
          if (/^youtube\s*·/i.test(text)) return 'youtube.com';
          if (/^rss\s*·\s*GeekNews\s*·/i.test(text)) return 'news.hada.io';
          if (/^rss\s*·\s*GitHub Trending - Daily\s*·/i.test(text)) return 'github.com';
          if (/^(rss|hackernews|github|reddit|telegram|twitter|youtube)\s*·/i.test(text)) break;
        }
        cursor = cursor.nextElementSibling;
      }
      return '';
    }

    var itemHosts = {};
    var itemHostsByOrder = [];
    document.querySelectorAll('.main-content h2 a[href^="http"]').forEach(function (link) {
      if (link.previousElementSibling && link.previousElementSibling.classList.contains('post-favicon')) return;
      var host = sourceHostFromHeading(link.parentElement) || hostFromUrl(link.href);
      if (!host) return;
      itemHostsByOrder.push(host);

      var anchor = link.parentElement && link.parentElement.previousElementSibling;
      if (anchor && anchor.id) itemHosts[anchor.id] = host;

      link.parentElement.insertBefore(makeIcon(host), link);
      link.parentElement.insertBefore(document.createTextNode(' '), link);
    });

    document.querySelectorAll('.main-content ol a[href^="#item-"]').forEach(function (link, index) {
      if (link.previousElementSibling && link.previousElementSibling.classList.contains('post-favicon')) return;
      var host = itemHosts[link.getAttribute('href').slice(1)] || itemHostsByOrder[index];
      if (!host) return;

      link.parentElement.insertBefore(makeIcon(host), link);
      link.parentElement.insertBefore(document.createTextNode(' '), link);
    });
  }

  /** Set up one-page source tabs for subscribed sites and YouTube */
  function setupSourceTabs() {
    var root = document.querySelector('[data-source-tabs]');
    if (!root) return;

    var tabs = root.querySelectorAll('[data-source-tab]');
    var panels = root.querySelectorAll('.source-tab-panel');

    function activate(name) {
      tabs.forEach(function (tab) {
        var selected = tab.getAttribute('data-source-tab') === name;
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      });

      panels.forEach(function (panel) {
        var selected = panel.id === 'source-panel-' + name;
        panel.classList.toggle('active', selected);
        panel.hidden = !selected;
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        activate(tab.getAttribute('data-source-tab'));
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    addPostFavicons();
    processScoreBadges();
    markSemanticElements();
    setupSourceTabs();
  });
})();
