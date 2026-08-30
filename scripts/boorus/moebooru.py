"""Client for Moebooru JSON API (Yande.re, Konachan)."""

import asyncio
from typing import Any
import aiohttp

from .base import (
    BooruClient,
    BooruConnectionException,
    BooruException,
    BooruPost,
    normalize_tag,
)
from .classifier import classify_tags


class MoebooruClient(BooruClient):
    """Client for Moebooru engines (yande.re, konachan)."""

    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 1.5

    def __init__(
        self,
        base_url: str = "https://yande.re/",
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(base_url, loop=loop)
        self._tag_type_cache: dict[str, int] = {}

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
        import random
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
            "limit": 20,
        }

        data = await self._request("/post.json", params)
        if not isinstance(data, list) or not data:
            return None

        valid_posts = [p for p in data if isinstance(p, dict) and p.get("id")]
        if not valid_posts:
            return None

        raw = random.choice(valid_posts)
        return await self._to_post(raw)

    async def _to_post(self, raw: dict[str, Any]) -> BooruPost:
        post_id = raw.get("id", "")
        file_url = raw.get("file_url") or raw.get("jpeg_url") or raw.get("sample_url") or raw.get("preview_url") or ""
        preview_url = raw.get("preview_url") or raw.get("sample_url") or file_url
        sample_url = raw.get("sample_url") or raw.get("jpeg_url") or file_url

        tags_str = html.unescape(str(raw.get("tags") or "")).strip()
        all_tags = [html.unescape(t) for t in tags_str.split()] if tags_str else []

        raw_rating = raw.get("rating", "s")
        rating_map = {"s": "safe", "q": "questionable", "e": "explicit"}
        norm_rating = rating_map.get(raw_rating, "safe")

        try:
            score = int(raw.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0

        post_url = f"{self._base_url}/post/show/{post_id}"

        # Fetch categorized tag types using Universal Tag Classifier
        tags_artist, tags_character, tags_copyright, tags_general, tags_meta = await classify_tags(
            all_tags, site_base_url=self._base_url
        )

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
            fav_count=0,
            source=raw.get("source") or "",
            width=int(raw.get("width", 0) or 0),
            height=int(raw.get("height", 0) or 0),
            created_at=str(raw.get("created_at") or ""),
        )

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
        }

        status_code = None
        data = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(self._base_url + path, params=params) as response:
                        status_code = response.status
                        text = await response.text()
                        if status_code in (200, 201):
                            try:
                                import json
                                data = json.loads(text)
                            except Exception:
                                data = text
                        elif status_code == 404:
                            data = []
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(f"Could not connect to {self._base_url} ({exc})") from exc

        if status_code == 404:
            return []
        if status_code not in (200, 201) and status_code is not None:
            raise BooruException(f"Moebooru returned status {status_code}")

        return data
