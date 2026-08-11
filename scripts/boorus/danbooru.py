"""Client for Danbooru's JSON API (also used by Danbooru-compatible mirrors).

Note: Danbooru sits behind Cloudflare bot protection that specifically
rejects clients *pretending* to be a browser (fake Mozilla/Chrome
User-Agents get a 403 challenge page). An honest, descriptive User-Agent
passes, so that's what we send.
"""
import asyncio

import aiohttp

from .base import BooruClient, BooruConnectionException, BooruException, BooruPost, normalize_tag

_USER_AGENT = "BooruTagsGacha/1.0 (Stable Diffusion WebUI extension)"


class DanbooruClient(BooruClient):
    # Danbooru caps searches at 2 tags for anonymous/free accounts, and
    # negated tags ("-tag") count toward that cap. So instead of sending
    # exclude tags as search terms (which triggers a 422 as soon as the
    # exclude list or the universal blacklist has a couple of entries),
    # exclusions are applied client-side by re-rolling posts that match.
    _EXCLUDE_REROLL_ATTEMPTS = 8

    def __init__(self, base_url="https://danbooru.donmai.us/", username=None, api_key=None, loop=None):
        self._base_url = (base_url or "https://danbooru.donmai.us/").rstrip('/')
        self._username = username
        self._api_key = api_key
        self._loop = loop

    def image_headers(self, url):
        # cdn.donmai.us sits behind the same Cloudflare rules as the API:
        # fake browser User-Agents get a 403 page instead of the image.
        return {"User-Agent": _USER_AGENT}

    async def random_post(self, tags=None, exclude_tags=None):
        include = [t.strip().lower().replace(' ', '_') for t in tags if t.strip()] if tags else []
        excluded = {normalize_tag(t) for t in exclude_tags if t.strip()} if exclude_tags else set()

        # /posts/random.json doesn't spend a tag slot on randomization the
        # way "random=true" on /posts.json does, so anonymous users keep
        # their full 2-tag budget for Include Tags.
        params = {"tags": ' '.join(include)} if include else {}

        attempts = self._EXCLUDE_REROLL_ATTEMPTS if excluded else 1
        for _ in range(attempts):
            data = await self._request("/posts/random.json", params)
            if not isinstance(data, dict) or not data.get('id'):
                return None
            post = self._to_post(data)
            if not any(normalize_tag(t) in excluded for t in post.tags):
                return post
        return None

    def _to_post(self, raw):
        post_id = raw.get('id')
        file_url = raw.get('file_url') or raw.get('large_file_url') or raw.get('preview_file_url')
        tags = (raw.get('tag_string') or '').split()
        rating = raw.get('rating')
        try:
            score = int(raw.get('score', 0) or 0)
        except (TypeError, ValueError):
            score = 0
        post_url = f"{self._base_url}/posts/{post_id}"

        post = BooruPost(post_id, file_url, tags, post_url, rating=rating, score=score)
        post.artist_tags = (raw.get('tag_string_artist') or '').split()
        return post

    # Networking knobs
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 2  # seconds, multiplied by attempt number

    async def _request(self, path, params):
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        auth = aiohttp.BasicAuth(self._username, self._api_key) if self._username and self._api_key else None

        status_code, content_type, data = None, None, None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(self._base_url + path, params=params, auth=auth) as response:
                        status_code = response.status
                        content_type = response.content_type
                        data = await response.json() if content_type == "application/json" else await response.text()
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(
                    f"Could not connect to {self._base_url} after {self._MAX_RETRIES} attempts: {exc}"
                ) from exc

        if status_code == 404:
            # /posts/random.json returns 404 when no post matches the tags.
            return {}
        if status_code == 403:
            raise BooruException(
                "Danbooru blocked the request (403 — likely a Cloudflare bot check). "
                "This can happen even with valid credentials; try again later or use a different site."
            )
        elif status_code == 401:
            raise BooruException("Danbooru returned 401 — check the username / API key in Settings")
        elif status_code == 422:
            raise BooruException(
                "Danbooru rejected the search — anonymous/free accounts can search at most "
                "2 tags at a time (Exclude Tags are handled locally and don't count)"
            )
        elif status_code not in (200, 201):
            raise BooruException(f"Danbooru returned a non-200 status code: {status_code}")

        if not isinstance(data, (list, dict)):
            raise BooruException("Danbooru returned an unexpected (non-JSON) response")

        return data
