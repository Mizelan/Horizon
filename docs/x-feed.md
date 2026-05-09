---
layout: default
title: X / Twitter Feed
---

# X / Twitter Feed

<p id="feed-meta">Loading...</p>

<div id="tweet-feed"></div>

<style>
#tweet-feed {
  display: flex;
  flex-direction: column;
  gap: 1em;
  margin: 1em 0;
}

.tweet-card {
  border: 1px solid var(--hz-border);
  border-radius: 8px;
  padding: 1em 1.2em;
  background: var(--hz-surface);
  transition: border-color 0.15s;
}

.tweet-card:hover {
  border-color: var(--hz-accent);
}

.tweet-header {
  display: flex;
  align-items: center;
  gap: 0.6em;
  margin-bottom: 0.5em;
}

.tweet-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
  background: var(--hz-border);
}

.tweet-author {
  font-weight: 700;
  color: var(--hz-text);
  text-decoration: none;
}

.tweet-handle {
  color: var(--hz-text-muted);
  font-size: 0.9em;
  margin-left: 0.3em;
}

.tweet-text {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--hz-text);
}

.tweet-text a {
  color: var(--hz-link);
}

.tweet-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1em;
  margin-top: 0.6em;
  font-size: 0.85em;
  color: var(--hz-text-muted);
}

.tweet-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.25em;
}

.tweet-time {
  color: var(--hz-text-muted);
  font-size: 0.85em;
}

.tweet-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.6em;
  padding-top: 0.6em;
  border-top: 1px solid var(--hz-border);
}

.tweet-open-link {
  font-size: 0.85em;
  color: var(--hz-link);
  text-decoration: none;
}

.tweet-open-link:hover {
  text-decoration: underline;
}

.score-pill {
  display: inline-block;
  padding: 0.1em 0.45em;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.8em;
  font-weight: 700;
  color: #fff;
}

.score-high { background: #be185d; }
.score-good { background: #e0652e; }
.score-mid  { background: #d4a017; }
.score-low  { background: #7c7891; }
.score-none { background: #7c7891; opacity: 0.5; }

@media (prefers-color-scheme: dark) {
  .tweet-card {
    border-color: #342f4a;
  }
  .tweet-card:hover {
    border-color: #e87040;
  }
}
</style>

<script>
(function () {
  var feedEl = document.getElementById('tweet-feed');
  var metaEl = document.getElementById('feed-meta');

  function timeAgo(iso) {
    var diff = Date.now() - new Date(iso).getTime();
    var min = Math.floor(diff / 60000);
    if (min < 1) return '방금';
    if (min < 60) return min + '분 전';
    var hrs = Math.floor(min / 60);
    if (hrs < 24) return hrs + '시간 전';
    var days = Math.floor(hrs / 24);
    return days + '일 전';
  }

  function formatDate(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString('ko-KR', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  function avatarUrl(handle) {
    return 'https://unavatar.io/x/' + encodeURIComponent(handle || 'x');
  }

  function scoreTier(score) {
    if (score == null) return 'none';
    if (score >= 9) return 'high';
    if (score >= 7) return 'good';
    if (score >= 5) return 'mid';
    return 'low';
  }

  function renderTweets(data) {
    if (!data || !data.tweets || data.tweets.length === 0) {
      feedEl.innerHTML = '<p style="color: var(--hz-text-muted);">아직 수집된 트윗이 없습니다.</p>';
      metaEl.textContent = data ? '마지막 업데이트: ' + formatDate(data.updated_at) : '';
      return;
    }

    metaEl.textContent = data.tweets.length + '개 트윗 · 마지막 업데이트: ' + timeAgo(data.updated_at);

    var html = '';
    for (var i = 0; i < data.tweets.length; i++) {
      var t = data.tweets[i];
      var tier = scoreTier(t.ai_score);
      var scoreLabel = t.ai_score != null ? t.ai_score.toFixed(1) : '—';
      var safeAuthor = esc(t.author);
      var safeHandle = esc(t.handle);
      var safeUrl = esc(t.url);
      var safeText = linkify(esc(t.text));
      html += '<div class="tweet-card">' +
        '<div class="tweet-header">' +
          '<img class="tweet-avatar" src="' + avatarUrl(safeHandle) + '" alt="' + safeHandle + '" loading="lazy" onerror="this.style.display=\'none\'">' +
          '<div>' +
            '<a class="tweet-author" href="https://twitter.com/' + encURI(safeHandle) + '" target="_blank" rel="noopener">' +
              safeAuthor +
            '</a>' +
            '<span class="tweet-handle">@' + safeHandle + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="tweet-text">' + safeText + '</div>' +
        '<div class="tweet-meta">' +
          '<span>❤️ ' + t.likes + '</span>' +
          '<span>🔁 ' + t.retweets + '</span>' +
          '<span>💬 ' + t.replies + '</span>' +
          '<span class="tweet-time">' + formatDate(t.created_at) + '</span>' +
        '</div>' +
        '<div class="tweet-footer">' +
          '<a class="tweet-open-link" href="' + safeUrl + '" target="_blank" rel="noopener">View on X ↗</a>' +
          '<span class="score-pill score-' + tier + '">' + scoreLabel + '</span>' +
        '</div>' +
      '</div>';
    }
    feedEl.innerHTML = html;
  }

  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function encURI(s) {
    return encodeURIComponent(s);
  }

  function linkify(s) {
    return s.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
            .replace(/@(\w+)/g, '<a href="https://twitter.com/$1" target="_blank" rel="noopener">@$1</a>');
  }

  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/Horizon/assets/data/twitter-feed.json', true);
  xhr.onload = function () {
    if (xhr.status === 200) {
      try { renderTweets(JSON.parse(xhr.responseText)); }
      catch (e) { feedEl.innerHTML = '<p style="color: var(--hz-text-muted);">데이터를 불러오는 중 오류가 발생했습니다.</p>'; }
    } else {
      feedEl.innerHTML = '<p style="color: var(--hz-text-muted);">트윗 피드를 불러올 수 없습니다.</p>';
      metaEl.textContent = '피드를 사용할 수 없음';
    }
  };
  xhr.onerror = function () {
    feedEl.innerHTML = '<p style="color: var(--hz-text-muted);">트윗 피드를 불러올 수 없습니다.</p>';
  };
  xhr.send();
})();
</script>
