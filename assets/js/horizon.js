(function () {
  'use strict';

  /** Replace ⭐️ N/10 with a colored badge in h2, h3, and li elements */
  function processScoreBadges() {
    var scoreRe = /⭐️\s*(\d+(?:\.\d+)?)\/10/;
    var targets = document.querySelectorAll('.main-content h2, .main-content h3, .main-content li, .main-content summary');
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

      var strong = p.querySelector('strong:first-child');
      if (strong && (strong.textContent === '배경' || strong.textContent === '토론')) {
        var nt = strong.nextSibling;
        if (nt && nt.nodeType === 3) nt.textContent = nt.textContent.replace(/^:\s*/, '');
        strong.remove();
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

  function updateUrlParam(key, value, defaultValue) {
    var url = new URL(window.location.href);
    if (value === defaultValue) {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
    history.replaceState(null, '', url.toString());
  }

  /** Set up one-page source tabs for subscribed sites and YouTube */
  function setupSourceTabs() {
    var root = document.querySelector('[data-source-tabs]');
    if (!root) return;

    var tabs = root.querySelectorAll('[data-source-tab]');
    var panels = root.querySelectorAll('.source-tab-panel');
    var firstTab = tabs.length ? tabs[0].getAttribute('data-source-tab') : null;

    function activate(name, updateUrl) {
      tabs.forEach(function (tab) {
        var selected = tab.getAttribute('data-source-tab') === name;
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      });

      panels.forEach(function (panel) {
        var selected = panel.id === 'source-panel-' + name;
        panel.classList.toggle('active', selected);
        panel.style.display = selected ? '' : 'none';
      });

      if (updateUrl !== false) updateUrlParam('tab', name, firstTab);
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        activate(tab.getAttribute('data-source-tab'));
      });
    });

    var initial = new URL(window.location.href).searchParams.get('tab');
    if (initial) activate(initial, false);
  }

  /** Set up sub-tabs within the sites source-tab panel */
  function setupSourceSubTabs() {
    var root = document.querySelector('[data-source-tabs]');
    if (!root) return;

    var subtabs = root.querySelectorAll('[data-source-subtab]');
    var subpanels = root.querySelectorAll('.source-subtab-panel');
    var firstSubtab = subtabs.length ? subtabs[0].getAttribute('data-source-subtab') : null;

    function activate(key, updateUrl) {
      subtabs.forEach(function (tab) {
        var selected = tab.getAttribute('data-source-subtab') === key;
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      });
      subpanels.forEach(function (panel) {
        var selected = panel.id === 'source-subpanel-' + key;
        panel.classList.toggle('active', selected);
        panel.style.display = selected ? '' : 'none';
      });

      if (updateUrl !== false) updateUrlParam('subtab', key, firstSubtab);
    }

    subtabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        activate(tab.getAttribute('data-source-subtab'));
      });
    });

    var initial = new URL(window.location.href).searchParams.get('subtab');
    if (initial) activate(initial, false);
  }

  /** Toggle the floating menu dropdown */
  function setupFloatMenu() {
    var btn = document.querySelector('.hz-menu-btn');
    var dropdown = document.querySelector('.hz-menu-dropdown');
    if (!btn || !dropdown) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', !expanded);
      dropdown.hidden = expanded;
    });

    document.addEventListener('click', function () {
      if (btn.getAttribute('aria-expanded') === 'true') {
        btn.setAttribute('aria-expanded', 'false');
        dropdown.hidden = true;
      }
    });

    dropdown.addEventListener('click', function (e) {
      e.stopPropagation();
    });

    dropdown.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        btn.setAttribute('aria-expanded', 'false');
        dropdown.hidden = true;
      });
    });
  }

  /** Add one-line summary tooltips to item links (h2, TOC, compact) */
  function addSummaryTooltips() {
    var tip = document.createElement('div');
    tip.id = 'hz-summary-tip';
    tip.className = 'hz-summary-tip';
    document.body.appendChild(tip);

    var isTouch = window.matchMedia('(pointer: coarse)').matches;
    var showTimer = null;
    var hideTimer = null;
    var activeEl = null;

    function positionTip(anchor) {
      var rect = anchor.getBoundingClientRect();
      var tipRect = tip.getBoundingClientRect();
      var top = rect.bottom + 6;
      var left = rect.left;
      if (left + tipRect.width > window.innerWidth - 8) left = window.innerWidth - 8 - tipRect.width;
      if (left < 8) left = 8;
      if (top + tipRect.height > window.innerHeight - 8) top = rect.top - tipRect.height - 6;
      tip.style.top = top + 'px';
      tip.style.left = left + 'px';
    }

    function showTip(anchor, text) {
      clearTimeout(hideTimer);
      clearTimeout(showTimer);
      showTimer = setTimeout(function () {
        tip.textContent = '”' + text + '”';
        tip.style.top = '0px';
        tip.style.left = '0px';
        tip.classList.add('visible');
        positionTip(anchor);
      }, 250);
    }

    function hideTip() {
      clearTimeout(showTimer);
      hideTimer = setTimeout(function () { tip.classList.remove('visible'); }, 100);
    }

    function attach(el, getTextFn) {
      if (isTouch) {
        // Touch: first tap shows tooltip, second tap navigates
        el.addEventListener('click', function (e) {
          var text = getTextFn();
          if (!text) return;
          if (activeEl === el) {
            // Second tap: navigate
            activeEl = null;
            tip.classList.remove('visible');
            return;
          }
          // First tap: show tooltip only
          e.preventDefault();
          activeEl = el;
          clearTimeout(showTimer);
          clearTimeout(hideTimer);
          tip.textContent = '”' + text + '”';
          tip.style.top = '0px';
          tip.style.left = '0px';
          tip.classList.add('visible');
          positionTip(el);
        });
      } else {
        el.addEventListener('mouseenter', function () {
          var text = getTextFn();
          if (text) showTip(el, text);
        });
        el.addEventListener('mouseleave', hideTip);
      }
    }

    // Dismiss tooltip on outside tap or scroll
    document.addEventListener('click', function (e) {
      if (activeEl && !activeEl.contains(e.target)) {
        activeEl = null;
        tip.classList.remove('visible');
      }
    });
    window.addEventListener('scroll', function () {
      if (activeEl) { activeEl = null; tip.classList.remove('visible'); }
    }, { passive: true });

    function blockquoteSummary(h2) {
      var next = h2 ? h2.nextElementSibling : null;
      if (next && next.tagName === 'BLOCKQUOTE') {
        var p = next.querySelector('p');
        if (p) return p.textContent.replace(/^[“”"']|[“”"']$/g, '').trim();
      }
      return '';
    }

    // h2 title links
    document.querySelectorAll('.main-content h2 a[href^="http"]').forEach(function (link) {
      attach(link, function () { return blockquoteSummary(link.closest('h2')); });
    });

    // TOC anchor links (#item-N)
    document.querySelectorAll('.main-content ol a[href^="#item-"]').forEach(function (link) {
      attach(link, function () {
        var target = document.getElementById(link.getAttribute('href').slice(1));
        if (!target) return '';
        var p = target.closest('p');
        var h2 = p ? p.nextElementSibling : null;
        return (h2 && h2.tagName === 'H2') ? blockquoteSummary(h2) : '';
      });
    });

    // Non-curated compact items — lazy: attach on details open
    function attachCompactLinks(root) {
      root.querySelectorAll('.hz-compact-title a:not([data-tip-ready])').forEach(function (link) {
        link.setAttribute('data-tip-ready', '1');
        attach(link, function () {
          var item = link.closest('.hz-compact-item');
          if (!item) return '';
          var summaryEl = item.querySelector('.hz-compact-summary');
          return summaryEl ? summaryEl.textContent.replace(/^[“””']|[“””']$/g, '').trim() : '';
        });
      });
    }

    document.addEventListener('toggle', function (e) {
      if (e.target.classList && e.target.classList.contains('hz-noncurated-details') && e.target.open) {
        attachCompactLinks(e.target);
      }
      // Accordion: when one hz-item-expand opens, close all others
      if (e.target.classList && e.target.classList.contains('hz-item-expand') && e.target.open) {
        document.querySelectorAll('.hz-item-expand[open]').forEach(function (details) {
          if (details !== e.target) {
            details.removeAttribute('open');
          }
        });
      }
    }, true);


  }

  /** Score popover: show ai_reason and score_breakdown on hover/click */
  function setupScorePopovers() {
    var BREAKDOWN_LABELS = {
      credibility: '출처 신뢰도',
      delta: '변화 규모',
      controversy: '커뮤니티 논쟁',
      urgency: '시간 압박',
      discussion_quality: '토론 품질',
    };
    var BREAKDOWN_ORDER = ['credibility', 'delta', 'controversy', 'urgency', 'discussion_quality'];

    var popover = document.getElementById('hz-popover');
    if (!popover) {
      popover = document.createElement('div');
      popover.id = 'hz-popover';
      popover.className = 'hz-popover';
      popover.setAttribute('role', 'tooltip');
      popover.setAttribute('aria-hidden', 'true');
      document.body.appendChild(popover);
    }

    var showTimer = null;
    var hideTimer = null;

    function hide() {
      clearTimeout(hideTimer);
      clearTimeout(showTimer);
      popover.classList.remove('visible');
      popover.setAttribute('aria-hidden', 'true');
    }

    function buildBreakdownBar(value) {
      var bar = document.createElement('div');
      bar.className = 'hz-breakdown-bar';
      var fill = document.createElement('div');
      fill.className = 'hz-breakdown-fill';
      fill.style.width = (value / 10 * 100) + '%';
      bar.appendChild(fill);
      return bar;
    }

    function buildBreakdownLabel(key) {
      return BREAKDOWN_LABELS[key] || key;
    }

    function positionAndShow(target, data) {
      popover.textContent = '';

      var reason = data.reason || '';
      var breakdown = data.breakdown;
      var score = data.score;
      var tier = data.tier;
      var hasBreakdown = breakdown && typeof breakdown === 'object' && Object.keys(breakdown).length > 0;

      // Header
      var header = document.createElement('div');
      header.className = 'hz-popover-header';
      var scoreSpan = document.createElement('span');
      scoreSpan.className = 'hz-popover-score';
      scoreSpan.setAttribute('data-tier', tier);
      scoreSpan.textContent = score;
      header.appendChild(scoreSpan);
      var label = document.createElement('span');
      label.className = 'hz-popover-label';
      label.textContent = 'AI Score';
      header.appendChild(label);
      popover.appendChild(header);

      // Breakdown dimensions
      if (hasBreakdown) {
        var bdWrap = document.createElement('div');
        bdWrap.className = 'hz-breakdown-wrap';
        var keys = BREAKDOWN_ORDER.filter(function (k) { return k in breakdown; });
        for (var bi = 0; bi < keys.length; bi++) {
          var key = keys[bi];
          var raw = breakdown[key];
          if (raw == null) continue;

          // Normalize: support both {score, reason} objects and plain numbers
          var dimScore, dimReason;
          if (typeof raw === 'number') {
            dimScore = raw;
            dimReason = '';
          } else {
            dimScore = raw.score;
            dimReason = raw.reason || '';
          }
          if (dimScore == null) continue;

          var row = document.createElement('div');
          row.className = 'hz-breakdown-row';

          var dimLabel = document.createElement('span');
          dimLabel.className = 'hz-breakdown-label';
          dimLabel.textContent = buildBreakdownLabel(key);
          row.appendChild(dimLabel);

          row.appendChild(buildBreakdownBar(dimScore));

          var dimScoreEl = document.createElement('span');
          dimScoreEl.className = 'hz-breakdown-score';
          dimScoreEl.textContent = dimScore;
          row.appendChild(dimScoreEl);

          // Per-dimension tooltip icon and popup
          if (dimReason) {
            var tipIcon = document.createElement('span');
            tipIcon.className = 'hz-dim-tip';
            tipIcon.textContent = '?';
            var tipPopup = document.createElement('span');
            tipPopup.className = 'hz-dim-popup';
            tipPopup.textContent = dimReason;
            tipIcon.appendChild(tipPopup);

            function positionPopup(p, pp) {
              pp.style.position = 'fixed';
              pp.style.top = '';
              pp.style.left = '';
              var pr = p.getBoundingClientRect();
              var ppRect = pp.getBoundingClientRect();
              var t = pr.bottom + 4;
              var l = pr.left + (pr.width / 2) - (ppRect.width / 2);
              if (l < 4) l = 4;
              if (l + ppRect.width > window.innerWidth - 4) l = window.innerWidth - 4 - ppRect.width;
              pp.style.top = t + 'px';
              pp.style.left = l + 'px';
              pp.classList.add('visible');
            }

            tipIcon.addEventListener('mouseenter', function (p, pp) {
              return function () { positionPopup(p, pp); };
            }(row, tipPopup));
            tipIcon.addEventListener('mouseleave', function () {
              var pp = this.querySelector('.hz-dim-popup');
              if (pp && !pp.classList.contains('pinned')) pp.classList.remove('visible');
            });

            tipIcon.addEventListener('click', function (p, pp) {
              return function (e) {
                e.stopPropagation();
                // Close other pinned popups
                document.querySelectorAll('.hz-dim-popup.pinned').forEach(function (el) {
                  el.classList.remove('visible', 'pinned');
                });
                if (pp.classList.contains('pinned')) {
                  pp.classList.remove('visible', 'pinned');
                  return;
                }
                positionPopup(p, pp);
                pp.classList.add('pinned');
              };
            }(row, tipPopup));

            row.appendChild(tipIcon);
          }

          bdWrap.appendChild(row);
        }
        if (bdWrap.children.length > 0) {
          popover.appendChild(bdWrap);
        }
      }

      // Reason text
      if (reason) {
        var body = document.createElement('div');
        body.className = 'hz-popover-body';
        body.textContent = reason;
        popover.appendChild(body);
      }

      if (popover.children.length <= 1) return;

      // Position
      popover.style.position = 'fixed';
      popover.style.top = '0px';
      popover.style.left = '0px';
      popover.classList.add('visible');

      var anchorRect = target.getBoundingClientRect();
      var popRect = popover.getBoundingClientRect();
      var popH = popRect.height;
      var popW = popRect.width;

      var top = anchorRect.bottom + 6;
      var left = anchorRect.left + (anchorRect.width / 2) - (popW / 2);

      if (left < 8) left = 8;
      if (left + popW > window.innerWidth - 8) left = window.innerWidth - 8 - popW;

      if (top + popH > window.innerHeight - 8) {
        top = anchorRect.top - popH - 6;
      }
      if (top < 8) top = 8;

      popover.style.top = top + 'px';
      popover.style.left = left + 'px';
      popover.setAttribute('aria-hidden', 'false');
    }

    function getScoreData(badge) {
      var reason = '';
      var breakdown = null;
      var sibling = badge.nextElementSibling;

      if (sibling && sibling.classList.contains('score-reason')) {
        reason = sibling.getAttribute('data-reason') || '';
        var bdRaw = sibling.getAttribute('data-breakdown');
        if (bdRaw) {
          try { breakdown = JSON.parse(bdRaw); } catch (e) { /* ignore parse errors */ }
        }
      }

      // Fallback: old format stored reason in textContent
      if (!reason && sibling && sibling.classList.contains('score-reason')) {
        reason = sibling.textContent.trim();
      }

      // Fallback: data-reason on badge itself (x-feed page)
      if (!reason) {
        reason = badge.getAttribute('data-reason') || '';
      }

      // Fallback: x-feed page stores JSON-ified breakdown in data-breakdown
      if (!breakdown) {
        var badgeBd = badge.getAttribute('data-breakdown');
        if (badgeBd) {
          try { breakdown = JSON.parse(badgeBd); } catch (e) { /* ignore */ }
        }
      }

      return { reason: reason, breakdown: breakdown };
    }

    var isTouchScore = window.matchMedia('(pointer: coarse)').matches;

    function attachPopover(badge) {
      var data = getScoreData(badge);
      if (!data.reason && !data.breakdown) return;

      data.score = badge.textContent;
      data.tier = badge.getAttribute('data-tier') ||
                  (badge.className.match(/score-(\w+)/) || [])[1] ||
                  'low';

      if (isTouchScore) {
        // Touch: first tap = show popover, second tap or outside = hide
        badge.addEventListener('click', function (e) {
          e.stopPropagation();
          clearTimeout(showTimer);
          clearTimeout(hideTimer);
          if (popover.classList.contains('visible') && popover._anchor === badge) {
            hide();
            popover._anchor = null;
          } else {
            positionAndShow(badge, data);
            popover._anchor = badge;
          }
        });
      } else {
        badge.addEventListener('mouseenter', function () {
          clearTimeout(hideTimer);
          clearTimeout(showTimer);
          showTimer = setTimeout(function () {
            positionAndShow(badge, data);
          }, 350);
        });

        badge.addEventListener('mouseleave', function () {
          clearTimeout(showTimer);
          hideTimer = setTimeout(hide, 200);
        });

        badge.addEventListener('click', function (e) {
          e.stopPropagation();
          clearTimeout(showTimer);
          clearTimeout(hideTimer);
          if (popover.classList.contains('visible')) {
            hide();
          } else {
            positionAndShow(badge, data);
          }
        });
      }
    }

    popover.addEventListener('mouseenter', function () {
      clearTimeout(hideTimer);
    });
    popover.addEventListener('mouseleave', function () {
      hideTimer = setTimeout(function () {
        document.querySelectorAll('.hz-dim-popup.visible').forEach(function (el) { el.classList.remove('visible'); });
        hide();
      }, 200);
    });

    // Close dimension tooltips when clicking the popover background
    popover.addEventListener('click', function () {
      document.querySelectorAll('.hz-dim-popup.visible').forEach(function (el) { el.classList.remove('visible'); });
    });

    document.addEventListener('click', function (e) {
      if (popover.classList.contains('visible') && !popover.contains(e.target)) {
        hide();
      }
    });

    window.addEventListener('scroll', function () {
      if (popover.classList.contains('visible')) hide();
    }, { passive: true });

    document.querySelectorAll('.score-badge').forEach(attachPopover);

    window.Horizon = window.Horizon || {};
    window.Horizon.attachScorePopover = attachPopover;
  }

  function openExternalLinksInNewTab() {
    var origin = location.origin;
    document.querySelectorAll('.main-content a[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      if (href && !href.startsWith('#') && !href.startsWith('/') && !href.startsWith(origin)) {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
      }
    });
  }

  function setupBackToTop() {
    if (window.matchMedia('(pointer: coarse)').matches) return;
    var btn = document.createElement('button');
    btn.className = 'hz-back-top';
    btn.setAttribute('aria-label', '맨 위로');
    btn.textContent = '↑';
    document.body.appendChild(btn);
    window.addEventListener('scroll', function () {
      btn.classList.toggle('visible', window.scrollY > 400);
    }, { passive: true });
    btn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  function setupSwipeSourceTabs() {
    var root = document.querySelector('[data-source-tabs]');
    if (!root) return;
    var tabs = Array.from(root.querySelectorAll('[data-source-tab]'));
    if (tabs.length < 2) return;
    var startX = 0, startY = 0;
    root.addEventListener('touchstart', function (e) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });
    root.addEventListener('touchend', function (e) {
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      var activeIdx = tabs.findIndex(function (t) { return t.classList.contains('active'); });
      var dir = dx < 0 ? 1 : -1;
      var nextIdx = activeIdx + dir;
      while (nextIdx >= 0 && nextIdx < tabs.length) {
        var cnt = tabs[nextIdx].querySelector('.source-tab-count');
        if (!cnt || parseInt(cnt.textContent, 10) !== 0) break;
        nextIdx += dir;
      }
      if (nextIdx >= 0 && nextIdx < tabs.length) tabs[nextIdx].click();
    }, { passive: true });
  }

  function setupSubtabScrollHint() {
    document.querySelectorAll('.source-subtablist').forEach(function (list) {
      var wrap = document.createElement('div');
      wrap.className = 'hz-subtablist-wrap';
      list.parentNode.insertBefore(wrap, list);
      wrap.appendChild(list);
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    addPostFavicons();
    processScoreBadges();
    markSemanticElements();
    setupSourceTabs();
    setupSourceSubTabs();
    setupFloatMenu();
    setupScorePopovers();
    openExternalLinksInNewTab();
    setupBackToTop();
    setupSwipeSourceTabs();
    setupSubtabScrollHint();
    addSummaryTooltips();
  });
})();
