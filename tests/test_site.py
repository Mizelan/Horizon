"""Tests for the site scraper (Anthropic Blog, Tildes, Refetch)."""

import asyncio
import json
from datetime import datetime, timezone

import httpx

import src.scrapers.site as site_module
from src.models import SiteConfig, SiteSourceConfig
from src.scrapers.site import SiteScraper


class FakeProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self._stdout = stdout.encode()
        self._stderr = stderr.encode()
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


def run(coro):
    return asyncio.run(coro)


def make_scraper(config: SiteConfig) -> SiteScraper:
    return SiteScraper(config, httpx.AsyncClient())


TEST_SINCE = datetime(2026, 3, 26, tzinfo=timezone.utc)  # includes Apr articles, filters Mar 25

ANTHROPIC_LISTING_HTML = """<html><body>
<article>
  <a href="/engineering/april-23-postmortem">An update on recent Claude Code quality reports</a>
  Apr 23, 2026
</article>
<article>
  <a href="/engineering/managed-agents">Scaling Managed Agents: Decoupling the brain from the hands</a>
  Apr 08, 2026
</article>
<article>
  <a href="/engineering/claude-code-auto-mode">Claude Code auto mode: a safer way to skip permissions</a>
  Mar 25, 2026
</article>
</body></html>"""

ANTHROPIC_ARTICLE_HTML = """<html><body>
<h1>An update on recent Claude Code quality reports</h1>
<time>Published Apr 23, 2026</time>
<p>Over the past month, we've been looking into reports...</p>
<p>All three issues have now been resolved.</p>
</body></html>"""


# --- Anthropic Blog ---

def test_anthropic_blog_parse_listing():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.startswith("/engineering/") and request.url.path != "/engineering/":
            return httpx.Response(200, text=ANTHROPIC_ARTICLE_HTML)
        if request.url.path == "/engineering":
            return httpx.Response(200, text=ANTHROPIC_LISTING_HTML)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Anthropic", url="https://www.anthropic.com/engineering", type="anthropic_blog")]),
        client,
    )

    items = run(scraper.fetch(TEST_SINCE))
    run(client.aclose())

    assert len(items) == 2
    assert items[0].title == "An update on recent Claude Code quality reports"
    assert items[1].title == "Scaling Managed Agents: Decoupling the brain from the hands"
    assert all(item.source_type.value == "site" for item in items)
    assert items[0].metadata["site_name"] == "Anthropic"
    assert items[0].metadata["site_type"] == "anthropic_blog"
    assert "Over the past month" in (items[0].content or "")


def test_anthropic_blog_disabled():
    scraper = make_scraper(SiteConfig(enabled=False, sites=[]))
    assert run(scraper.fetch(TEST_SINCE)) == []


def test_anthropic_blog_empty_listing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>No articles here</body></html>")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Empty", url="https://www.anthropic.com/engineering", type="anthropic_blog")]),
        client,
    )

    items = run(scraper.fetch(TEST_SINCE))
    run(client.aclose())
    assert items == []


def test_anthropic_blog_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Error", url="https://www.anthropic.com/engineering", type="anthropic_blog")]),
        client,
    )

    items = run(scraper.fetch(TEST_SINCE))
    run(client.aclose())
    assert items == []


# --- Tildes ---

TILDES_HTML = """<html><body>
<article class="topic">
  <h1 class="topic-title">
    <a href="https://example.com/linux-tips">Linux kernel 6.10 released</a>
  </h1>
  <div class="topic-metadata">
    <span class="topic-group"><a class="link-group" href="https://tildes.net/~comp">~comp</a></span>
    <span class="topic-content-type">Link</span>
  </div>
  <footer class="topic-info">
    <div class="topic-info-comments"><a href="https://tildes.net/~comp/123">15 comments</a></div>
    <div class="topic-info-source">example.com</div>
    3 hours ago
  </footer>
  <div class="topic-voting">
    <div class="topic-voting-inner">42</div>
  </div>
</article>
<article class="topic">
  <h1 class="topic-title">
    <a href="https://news.ycombinator.com/item?id=1">Ask HN: Best code editor?</a>
  </h1>
  <div class="topic-metadata">
    <span class="topic-group">~talk</span>
  </div>
  <footer class="topic-info">
    <div class="topic-info-comments">8 comments</div>
    1 day ago
  </footer>
</article>
</body></html>"""


def test_tildes_parse_listing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=TILDES_HTML)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Tildes", url="https://tildes.net/", type="tildes")]),
        client,
    )

    items = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))
    run(client.aclose())

    assert len(items) == 2
    assert items[0].title == "Linux kernel 6.10 released"
    assert items[0].author == "~comp"
    assert items[0].metadata["group"] == "~comp"
    assert items[0].metadata["score"] == 42
    assert items[0].metadata["num_comments"] == 15
    assert items[1].title == "Ask HN: Best code editor?"
    assert items[1].metadata["score"] == 0


def test_tildes_fetch_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=TILDES_HTML)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Tildes", url="https://tildes.net/", type="tildes", fetch_limit=1)]),
        client,
    )

    items = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))
    run(client.aclose())

    assert len(items) == 1


# --- Refetch ---

def test_refetch_subprocess(monkeypatch):
    calls = []

    fake_json = json.dumps({
        "title": "Refetch - Latest Tech News",
        "articles": [
            {"title": "Can LLMs Model Real-World Systems in TLA+?", "url": "https://sigops.org/2026/tla", "date_text": "1 hour ago"},
            {"title": "AWS North Virginia Data Center Outage", "url": "https://cnbc.com/aws-outage", "date_text": "3 hours ago"},
            {"title": "Old article that should be filtered", "url": "https://example.com/old", "date_text": "30 days ago"},
        ]
    })

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        return FakeProcess(fake_json)

    monkeypatch.setattr(site_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    scraper = make_scraper(
        SiteConfig(
            sites=[SiteSourceConfig(name="Refetch", url="https://refetch.io/", type="refetch", fetch_limit=10)],
            playwright_python="/mock/python3",
        )
    )
    scraper._playwright_python = "/mock/python3"  # bypass detection

    items = run(scraper.fetch(datetime(2026, 5, 8, tzinfo=timezone.utc)))

    assert len(items) == 2
    assert items[0].title == "Can LLMs Model Real-World Systems in TLA+?"
    assert items[1].title == "AWS North Virginia Data Center Outage"
    assert all(item.source_type.value == "site" for item in items)
    assert all(item.metadata["site_name"] == "Refetch" for item in items)


def test_refetch_subprocess_timeout(monkeypatch):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess("")

    async def fake_wait_for(coro, timeout):
        await coro
        raise TimeoutError

    monkeypatch.setattr(site_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(site_module.asyncio, "wait_for", fake_wait_for)
    scraper = make_scraper(
        SiteConfig(
            sites=[SiteSourceConfig(name="Refetch", url="https://refetch.io/", type="refetch")],
            playwright_python="/mock/python3",
        )
    )
    scraper._playwright_python = "/mock/python3"

    items = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))
    assert items == []


def test_refetch_subprocess_nonzero_exit(monkeypatch):
    async def fake_process(*args, **kwargs):
        return FakeProcess("", "error: chromium not found", returncode=1)

    monkeypatch.setattr(site_module.asyncio, "create_subprocess_exec", fake_process)
    scraper = make_scraper(
        SiteConfig(
            sites=[SiteSourceConfig(name="Refetch", url="https://refetch.io/", type="refetch")],
            playwright_python="/mock/python3",
        )
    )
    scraper._playwright_python = "/mock/python3"

    items = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))
    assert items == []


def test_refetch_invalid_json(monkeypatch):
    async def fake_process(*args, **kwargs):
        return FakeProcess("{not valid json")

    monkeypatch.setattr(site_module.asyncio, "create_subprocess_exec", fake_process)
    scraper = make_scraper(
        SiteConfig(
            sites=[SiteSourceConfig(name="Refetch", url="https://refetch.io/", type="refetch")],
            playwright_python="/mock/python3",
        )
    )
    scraper._playwright_python = "/mock/python3"

    items = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))
    assert items == []


# --- Utilities ---

def test_parse_relative_time():
    now = datetime.now(timezone.utc)

    result = SiteScraper._parse_relative_time("3 hours ago")
    assert result is not None
    diff = (now - result).total_seconds()
    assert 2.5 * 3600 < diff < 3.5 * 3600

    result = SiteScraper._parse_relative_time("1 day ago")
    assert result is not None
    diff = (now - result).total_seconds()
    assert 0.5 * 86400 < diff < 1.5 * 86400

    result = SiteScraper._parse_relative_time("30 minutes ago")
    assert result is not None
    diff = (now - result).total_seconds()
    assert 25 * 60 < diff < 35 * 60

    result = SiteScraper._parse_relative_time("no match here")
    assert result is None

    result = SiteScraper._parse_relative_time("")
    assert result is None


def test_try_parse_absolute_date():
    result = SiteScraper._try_parse_absolute_date("Apr 23, 2026")
    assert result is not None
    assert result.year == 2026
    assert result.month == 4
    assert result.day == 23
    assert result.tzinfo is not None

    result = SiteScraper._try_parse_absolute_date("not a date")
    assert result is None


def test_extract_anthropic_date():
    result = SiteScraper._extract_anthropic_date("Some text Apr 08, 2026 and more")
    assert result is not None
    assert result.month == 4
    assert result.day == 8

    result = SiteScraper._extract_anthropic_date("No date here")
    assert result is None


# --- Config and edge cases ---

def test_site_disabled_config():
    scraper = make_scraper(SiteConfig(enabled=False, sites=[
        SiteSourceConfig(name="Test", url="https://example.com", type="anthropic_blog"),
    ]))
    assert run(scraper.fetch(TEST_SINCE)) == []


def test_unknown_site_type():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[SiteSourceConfig(name="Unknown", url="https://example.com", type="nonexistent")]),
        client,
    )

    items = run(scraper.fetch(TEST_SINCE))
    run(client.aclose())
    assert items == []


def test_no_sites_configured():
    scraper = make_scraper(SiteConfig(enabled=True, sites=[]))
    assert run(scraper.fetch(TEST_SINCE)) == []


def test_mixed_sites_independent_failure():
    """One failing site shouldn't prevent others from returning results."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500)
        return httpx.Response(200, text=ANTHROPIC_LISTING_HTML)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = SiteScraper(
        SiteConfig(sites=[
            SiteSourceConfig(name="Fail", url="https://fail.com", type="anthropic_blog"),
            SiteSourceConfig(name="OK", url="https://www.anthropic.com/engineering", type="anthropic_blog"),
        ]),
        client,
    )

    items = run(scraper.fetch(TEST_SINCE))
    run(client.aclose())
    assert len(items) > 0
