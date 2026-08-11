"""Client for e621's JSON API (also works for e926, the SFW mirror).

e621 requires a descriptive User-Agent and rate-limits to ~2 requests/sec.
Credentials (username + API key) are optional; without them the site's
default global blacklist hides some posts' file URLs.
"""
import asyncio

import aiohttp

from .base import BooruClient, BooruConnectionException, BooruException, BooruPost

_USER_AGENT = "BooruTagsGacha/1.0 (Stable Diffusion WebUI extension)"

# Tags e621 files under the "artist" category that aren't actually artists.
_NON_ARTIST_TAGS = {
    "conditional_dnp", "avoid_posting", "unknown_artist", "anonymous_artist",
    "sound_warning", "epilepsy_warning", "third-party_edit",
}


class E621Client(BooruClient):
    def __init__(self, base_url="https://e621.net/", username=None, api_key=None, loop=None):
        self._base_url = (base_url or "https://e621.net/").rstrip('/')
        self._username = username
        self._api_key = api_key
        self._loop = loop

    def image_headers(self, url):
        # e621's policy asks for a descriptive User-Agent on every request.
        return {"User-Agent": _USER_AGENT}

    async def random_post(self, tags=None, exclude_tags=None):
        # e621 allows up to 40 search terms, so excludes can go straight
        # into the query. order:random counts as one of them.
        formatted = ["order:random"] + self._format_tags(tags, exclude_tags)
        params = {"limit": "1", "tags": ' '.join(formatted)}

        data = await self._request("/posts.json", params)
        posts = data.get("posts") if isinstance(data, dict) else None
        if not posts:
            return None
        return self._to_post(posts[0])

    def _to_post(self, raw):
        post_id = raw.get('id')

        # file.url is null for guests when the post is on e621's default
        # global blacklist; fall back to the sample/preview renders.
        file_url = None
        for key in ('file', 'sample', 'preview'):
            node = raw.get(key) or {}
            if node.get('url'):
                file_url = node['url']
                break

        tag_groups = raw.get('tags') or {}
        tags = []
        for group in ('artist', 'character', 'copyright', 'species', 'general', 'meta', 'lore'):
            tags.extend(tag_groups.get(group) or [])

        rating = raw.get('rating')
        try:
            score = int((raw.get('score') or {}).get('total', 0) or 0)
        except (TypeError, ValueError):
            score = 0
        post_url = f"{self._base_url}/posts/{post_id}"

        post = BooruPost(post_id, file_url, tags, post_url, rating=rating, score=score)
        post.artist_tags = [t for t in (tag_groups.get('artist') or []) if t not in _NON_ARTIST_TAGS]
        return post

    def _format_tags(self, tags, exclude_tags):
        tags = [t.strip().lower().replace(' ', '_') for t in tags if t.strip()] if tags else []
        exclude_tags = ['-' + t.strip().lstrip('-').lower().replace(' ', '_') for t in exclude_tags if t.strip()] if exclude_tags else []
        return tags + exclude_tags

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

        if status_code == 401:
            raise BooruException("e621 returned 401 — check the username / API key in Settings")
        elif status_code == 403:
            raise BooruException("e621 returned 403 (access denied)")
        elif status_code == 503:
            raise BooruException("e621 returned 503 — rate limited, wait a moment and try again")
        elif status_code not in (200, 201):
            raise BooruException(f"e621 returned a non-200 status code: {status_code}")

        if not isinstance(data, dict):
            raise BooruException("e621 returned an unexpected (non-JSON) response")

        return data
