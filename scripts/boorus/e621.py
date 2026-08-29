"""Client for e621 and e926 JSON API."""

import asyncio
from typing import Any
import aiohttp

from .base import (
    BooruClient,
    BooruConnectionException,
    BooruException,
    BooruAuthException,
    BooruRateLimitException,
    BooruPost,
    normalize_tag,
)

_NON_ARTIST_TAGS = {
    "conditional_dnp", "avoid_posting", "unknown_artist", "anonymous_artist",
    "sound_warning", "epilepsy_warning", "third-party_edit",
}


class E621Client(BooruClient):
    """Client for e621 (https://e621.net/) and e926 (https://e926.net/)."""

    _USER_AGENT = "BooruTagsGacha/2.0 (Stable Diffusion WebUI extension; contact: User)"
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 1.5

    def __init__(
        self,
        base_url: str = "https://e621.net/",
        username: str | None = None,
        api_key: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(base_url, loop=loop)
        self._username = username.strip() if username else None
        self._api_key = api_key.strip() if api_key else None

    def image_headers(self, url: str) -> dict[str, str]:
        return {
            "User-Agent": self._USER_AGENT,
            "Referer": self._base_url,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

    async def random_post(
        self,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> BooruPost | None:
        include = [normalize_tag(t) for t in (tags or []) if t.strip()]
        excluded = [f"-{normalize_tag(t)}" for t in (exclude_tags or []) if t.strip()]

        query_terms = ["order:random"]
        if rating and rating != "any":
            rating_char = "s" if rating == "safe" else ("q" if rating == "questionable" else "e")
            query_terms.append(f"rating:{rating_char}")

        if min_score > 0:
            query_terms.append(f"score:>={min_score}")

        query_terms.extend(include)
        query_terms.extend(excluded)

        params = {
            "tags": ' '.join(query_terms),
            "limit": 1,
        }

        data = await self._request("/posts.json", params)
        posts = data.get("posts") if isinstance(data, dict) else None
        if not posts or not isinstance(posts, list):
            return None

        return self._to_post(posts[0])

    def _to_post(self, raw: dict[str, Any]) -> BooruPost:
        post_id = raw.get("id", "")
        
        file_url = None
        for key in ("file", "sample", "preview"):
            node = raw.get(key) or {}
            if node.get("url"):
                file_url = node["url"]
                break
        file_url = file_url or ""
        
        preview_node = raw.get("preview") or {}
        preview_url = preview_node.get("url") or file_url

        sample_node = raw.get("sample") or {}
        sample_url = sample_node.get("url") or file_url

        tag_groups = raw.get("tags") or {}
        tags_artist = [t for t in (tag_groups.get("artist") or []) if t not in _NON_ARTIST_TAGS]
        tags_character = tag_groups.get("character") or []
        tags_copyright = tag_groups.get("copyright") or []
        tags_species = tag_groups.get("species") or []
        tags_general = (tag_groups.get("general") or []) + tags_species
        tags_meta = (tag_groups.get("meta") or []) + (tag_groups.get("lore") or [])

        all_tags = []
        for g in ("artist", "character", "copyright", "species", "general", "meta", "lore"):
            all_tags.extend(tag_groups.get(g) or [])

        raw_rating = raw.get("rating", "s")
        rating_map = {"s": "safe", "q": "questionable", "e": "explicit"}
        norm_rating = rating_map.get(raw_rating, "safe")

        try:
            score = int((raw.get("score") or {}).get("total", 0) or 0)
        except (TypeError, ValueError):
            score = 0

        try:
            fav_count = int(raw.get("fav_count", 0) or 0)
        except (TypeError, ValueError):
            fav_count = 0

        post_url = f"{self._base_url}/posts/{post_id}"

        return BooruPost(
            id=post_id,
            post_url=post_url,
            file_url=file_url,
            preview_url=preview_url,
            sample_url=sample_url,
            tags_general=tags_general,
            tags_character=tags_character,
            tags_copyright=tags_copyright,
            tags_artist=tags_artist,
            tags_meta=tags_meta,
            all_tags=all_tags,
            rating=norm_rating,
            score=score,
            fav_count=fav_count,
            source=str(raw.get("sources") or ""),
            width=int((raw.get("file") or {}).get("width", 0) or 0),
            height=int((raw.get("file") or {}).get("height", 0) or 0),
            created_at=str(raw.get("created_at") or ""),
        )

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
        }
        auth = (
            aiohttp.BasicAuth(self._username, self._api_key)
            if self._username and self._api_key
            else None
        )

        status_code = None
        data = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(self._base_url + path, params=params, auth=auth) as response:
                        status_code = response.status
                        if response.content_type == "application/json":
                            data = await response.json()
                        else:
                            text = await response.text()
                            if status_code == 200:
                                data = text
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(f"Could not connect to {self._base_url} ({exc})") from exc

        if status_code == 401:
            raise BooruAuthException("e621 returned 401 Unauthorized — check username and API key.")
        if status_code == 403:
            raise BooruException("e621 returned 403 Forbidden.")
        if status_code == 503:
            raise BooruRateLimitException("e621 returned 503 — rate limit exceeded, please wait a moment.")
        if status_code not in (200, 201):
            raise BooruException(f"e621 returned status {status_code}")

        return data
