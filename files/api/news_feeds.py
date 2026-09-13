"""Configurable external information-feed helpers for FloodWatch.

The dashboard should not hardcode old "news" cards and pretend they are live.
This module fetches real articles only when a provider is configured through
environment variables. If no provider is configured, the API returns an honest
"not configured" response so the user knows which key is missing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


NEWS_TIMEOUT_SECONDS = 8
NEWS_CACHE_SECONDS = 5 * 60
DEFAULT_NEWS_QUERY = 'flood OR rainfall OR "heavy rain" Nigeria'
_CACHE: dict[str, object] = {}


def configured_provider() -> str:
    """Return the selected provider without exposing secret values."""
    requested = os.getenv("FLOOD_EWS_NEWS_PROVIDER", "auto").strip().lower()
    if requested in {"newsapi", "gnews", "rss", "off"}:
        return requested
    return "auto"


def news_query() -> str:
    """Use an environment-defined search phrase or the flood-focused default."""
    return os.getenv("FLOOD_EWS_NEWS_QUERY", DEFAULT_NEWS_QUERY).strip() or DEFAULT_NEWS_QUERY


def _parse_datetime(value: str | None) -> datetime | None:
    """Convert provider timestamps to timezone-aware datetimes when possible."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def safe_article_url(value: str | None) -> str:
    """Accept only web links so provider text cannot become executable URLs."""
    if not isinstance(value, str):
        return ""
    try:
        parsed = urllib.parse.urlsplit(value.strip())
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password:
            return value.strip()
    except ValueError:
        pass
    return ""


def _http_json(url: str, headers: dict[str, str] | None = None) -> dict:
    """Fetch a JSON document using only the Python standard library."""
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "FloodWatchPrototype/1.0"})
    with urllib.request.urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:  # nosec: URL is configured/operator controlled.
        content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Provider response exceeds size limit")
        return json.loads(content.decode("utf-8"))


def _http_text(url: str) -> str:
    """Fetch text data for RSS feeds with a short timeout."""
    if not safe_article_url(url):
        raise ValueError("RSS must use an HTTP or HTTPS URL")
    request = urllib.request.Request(url, headers={"User-Agent": "FloodWatchPrototype/1.0"})
    with urllib.request.urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:  # nosec: URL is configured/operator controlled.
        content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Provider response exceeds size limit")
        return content.decode("utf-8", errors="replace")


def _article(title: str, source: str, url: str, provider: str, published_at: str | None = None, description: str | None = None) -> dict:
    """Normalize provider-specific fields into one frontend-friendly shape."""
    return {
        "title": (title or "Untitled update").strip()[:220],
        "source": (source or provider).strip()[:120],
        "url": safe_article_url(url),
        "published_at": _parse_datetime(published_at),
        "description": (description or "").strip()[:420] or None,
        "provider": provider,
    }


def _fetch_newsapi(limit: int) -> dict:
    """Fetch articles from NewsAPI.org's Everything endpoint."""
    api_key = os.getenv("FLOOD_EWS_NEWSAPI_KEY", "").strip()
    if not api_key:
        return _not_configured("newsapi", "Set FLOOD_EWS_NEWSAPI_KEY to enable NewsAPI.org article search.")

    params = {
        "q": news_query(),
        "language": os.getenv("FLOOD_EWS_NEWS_LANGUAGE", "en").strip() or "en",
        "sortBy": "publishedAt",
        "pageSize": str(max(1, min(limit, 20))),
    }
    url = "https://newsapi.org/v2/everything?" + urllib.parse.urlencode(params)
    data = _http_json(url, headers={"X-Api-Key": api_key, "User-Agent": "FloodWatchPrototype/1.0"})
    if data.get("status") == "error":
        raise ValueError("Provider rejected the request")
    articles = [
        _article(
            item.get("title"),
            (item.get("source") or {}).get("name") or "NewsAPI source",
            item.get("url"),
            "newsapi",
            item.get("publishedAt"),
            item.get("description"),
        )
        for item in data.get("articles", [])[:limit]
        if item.get("url")
    ]
    return _payload(True, "newsapi", articles, "NewsAPI articles retrieved. Publication delays depend on your provider plan.")


def _fetch_gnews(limit: int) -> dict:
    """Fetch articles from the GNews search endpoint."""
    api_key = os.getenv("FLOOD_EWS_GNEWS_API_KEY", "").strip()
    if not api_key:
        return _not_configured("gnews", "Set FLOOD_EWS_GNEWS_API_KEY to enable GNews article search.")

    params = {
        "q": news_query(),
        "lang": os.getenv("FLOOD_EWS_NEWS_LANGUAGE", "en").strip() or "en",
        "max": str(max(1, min(limit, 10))),
    }
    country = os.getenv("FLOOD_EWS_NEWS_COUNTRY", "").strip().lower()
    if country:
        params["country"] = country

    url = "https://gnews.io/api/v4/search?" + urllib.parse.urlencode(params)
    data = _http_json(url, headers={"X-Api-Key": api_key, "User-Agent": "FloodWatchPrototype/1.0"})
    if data.get("errors"):
        raise ValueError("Provider rejected the request")
    articles = [
        _article(
            item.get("title"),
            (item.get("source") or {}).get("name") or "GNews source",
            item.get("url"),
            "gnews",
            item.get("publishedAt"),
            item.get("description"),
        )
        for item in data.get("articles", [])[:limit]
        if item.get("url")
    ]
    return _payload(True, "gnews", articles, "GNews articles retrieved. Publication delays depend on your provider plan.")


def _fetch_rss(limit: int) -> dict:
    """Fetch configured RSS URLs for institutions or news outlets."""
    feed_urls = [url.strip() for url in os.getenv("FLOOD_EWS_RSS_FEEDS", "").split(",") if url.strip()]
    if not feed_urls:
        return _not_configured("rss", "Set FLOOD_EWS_RSS_FEEDS to one or more comma-separated RSS feed URLs.")

    articles: list[dict] = []
    for feed_url in feed_urls[:5]:
        try:
            root = ET.fromstring(_http_text(feed_url))
        except (ET.ParseError, OSError, TimeoutError, ValueError):
            continue
        channel_title = root.findtext("./channel/title") or "RSS feed"
        for item in root.findall("./channel/item"):
            articles.append(
                _article(
                    item.findtext("title"),
                    channel_title,
                    item.findtext("link"),
                    "rss",
                    item.findtext("pubDate"),
                    item.findtext("description"),
                )
            )
            if len(articles) >= limit:
                break
        if len(articles) >= limit:
            break

    return _payload(True, "rss", articles[:limit], "Configured RSS feed articles loaded." if articles else "RSS feeds were configured but no readable articles were returned.")


def _not_configured(provider: str, message: str) -> dict:
    """Return a transparent provider-missing payload."""
    return _payload(False, provider, [], message)


def _payload(configured: bool, provider: str, articles: list[dict], message: str) -> dict:
    """Create the normalized response shared by all providers."""
    return {
        "configured": configured,
        "provider": provider,
        "query": news_query(),
        "articles": [article for article in articles if article["url"]],
        "message": message,
        "fetched_at": datetime.now(timezone.utc),
    }


def fetch_news(limit: int = 8, *, force_refresh: bool = False) -> dict:
    """Fetch configured news/resources with a short cache to avoid API spam."""
    now = datetime.now(timezone.utc)
    # Include query, limit and configuration in the cache identity. Keys are
    # hashed only for comparison and never included in an API response.
    configuration = [os.getenv(name, "") for name in (
        "FLOOD_EWS_NEWS_PROVIDER", "FLOOD_EWS_NEWSAPI_KEY", "FLOOD_EWS_GNEWS_API_KEY",
        "FLOOD_EWS_RSS_FEEDS", "FLOOD_EWS_NEWS_QUERY", "FLOOD_EWS_NEWS_LANGUAGE", "FLOOD_EWS_NEWS_COUNTRY",
    )]
    cache_key = hashlib.sha256(json.dumps([configuration, limit]).encode()).hexdigest()
    cached_payload = _CACHE.get("payload")
    # A public refresh button still honours a 30-second floor to limit provider
    # quota use. Normal polling reuses the response for five minutes.
    if cached_payload and _CACHE.get("key") == cache_key and _CACHE["expires_at"] > now and (
        not force_refresh or _CACHE["refresh_after"] > now
    ):
        return cached_payload  # type: ignore[return-value]

    provider = configured_provider()
    try:
        if provider == "off":
            payload = _not_configured("off", "External news feeds are disabled by FLOOD_EWS_NEWS_PROVIDER=off.")
        elif provider == "newsapi" or (provider == "auto" and os.getenv("FLOOD_EWS_NEWSAPI_KEY")):
            payload = _fetch_newsapi(limit)
        elif provider == "gnews" or (provider == "auto" and os.getenv("FLOOD_EWS_GNEWS_API_KEY")):
            payload = _fetch_gnews(limit)
        elif provider == "rss" or (provider == "auto" and os.getenv("FLOOD_EWS_RSS_FEEDS")):
            payload = _fetch_rss(limit)
        else:
            payload = _not_configured("none", "No external news provider is configured yet.")
    except Exception:  # Provider errors can include secrets in their URLs: never echo them.
        payload = _payload(True, provider, [], "News provider temporarily unavailable. Check server configuration and provider limits.")

    _CACHE["payload"] = payload
    _CACHE["expires_at"] = now + timedelta(seconds=NEWS_CACHE_SECONDS)
    _CACHE["refresh_after"] = now + timedelta(seconds=30)
    _CACHE["key"] = cache_key
    return payload
