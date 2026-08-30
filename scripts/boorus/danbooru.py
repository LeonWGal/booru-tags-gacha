"""Client for Danbooru JSON API."""

import asyncio
from typing import Any
import aiohttp

from .base import (
    BooruClient,
    BooruConnectionException,
    BooruException,
    BooruAuthException,
    BooruPost,
    normalize_tag,
)


class DanbooruClient(BooruClient):
    """Client for Danbooru and Danbooru-compatible engines."""

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
        "BooruTagsGacha/2.0"
    )
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 1.5

    def __init__(
        self,
        base_url: str = "https://danbooru.donmai.us/",
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
        import random

        include = [normalize_tag(t) for t in (tags or []) if t.strip()]
        excluded = {normalize_tag(t) for t in (exclude_tags or []) if t.strip()}

        rating_map = {"safe": "g", "sensitive": "s", "questionable": "q", "explicit": "e"}
        norm_rating_char = rating_map.get(rating, None) if (rating and rating != "any") else None

        is_authenticated = bool(self._username and self._api_key)

        # Authenticated users: Danbooru accepts up to 40 tags in query
        if is_authenticated:
            query_terms = ["order:random"]
            if norm_rating_char:
                query_terms.append(f"rating:{norm_rating_char}")
            if min_score > 0:
                query_terms.append(f"score:>={min_score}")
            query_terms.extend(include)
            for ex in excluded:
                query_terms.append(f"-{ex}")

            params = {
                "tags": " ".join(query_terms),
                "limit": 1,
            }
            data = await self._request("/posts.json", params)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return self._to_post(data[0])
            return None

        # Anonymous users: Danbooru STRICTLY limits queries to MAX 2 tags!
        # Tag 1: order:random
        # Tag 2: first include tag or rating filter
        query_terms = ["order:random"]
        if include:
            query_terms.append(include[0])
        elif norm_rating_char:
            query_terms.append(f"rating:{norm_rating_char}")
        elif min_score > 0:
            query_terms.append(f"score:>={min_score}")

        params = {
            "tags": " ".join(query_terms),
            "limit": 40,
        }

        # Query candidate batch in a single fast request
        data = await self._request("/posts.json", params)
        if not isinstance(data, list) or not data:
            if include:
                data = await self._request("/posts.json", {"tags": include[0], "limit": 40})
            if not isinstance(data, list) or not data:
                return None

        # Filter candidates client-side
        candidates = []
        for raw in data:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue

            # Check rating
            if norm_rating_char:
                post_r = raw.get("rating", "g")
                if norm_rating_char == "g" and post_r not in ("g", "s"):
                    continue
                elif norm_rating_char in ("q", "e", "s") and post_r != norm_rating_char:
                    continue

            # Check min score
            try:
                post_score = int(raw.get("score", 0) or 0)
            except (TypeError, ValueError):
                post_score = 0
            if min_score > 0 and post_score < min_score:
                continue

            # Check remaining include tags
            post_all_tags = set((raw.get("tag_string") or "").split())
            if len(include) > 1:
                if not all(any(req == normalize_tag(t) for t in post_all_tags) for req in include[1:]):
                    continue

            # Check exclude tags
            if excluded and any(normalize_tag(t) in excluded for t in post_all_tags):
                continue

            candidates.append(raw)

        if not candidates:
            # Relax score or rating slightly if strict filtering had 0 matches
            for raw in data:
                post_all_tags = set((raw.get("tag_string") or "").split())
                if excluded and any(normalize_tag(t) in excluded for t in post_all_tags):
                    continue
                candidates.append(raw)

        if not candidates:
            return None

        selected_raw = random.choice(candidates)
        return self._to_post(selected_raw)

    def _to_post(self, raw: dict[str, Any]) -> BooruPost:
        post_id = raw.get("id", "")
        file_url = raw.get("file_url") or raw.get("large_file_url") or raw.get("preview_file_url") or ""
        preview_url = raw.get("preview_file_url") or raw.get("large_file_url") or file_url
        sample_url = raw.get("large_file_url") or file_url

        tags_artist = (raw.get("tag_string_artist") or "").split()
        tags_character = (raw.get("tag_string_character") or "").split()
        tags_copyright = (raw.get("tag_string_copyright") or "").split()
        tags_general = (raw.get("tag_string_general") or "").split()
        tags_meta = (raw.get("tag_string_meta") or "").split()
        all_tags = (raw.get("tag_string") or "").split()

        raw_rating = raw.get("rating", "g")
        rating_map = {"g": "safe", "s": "sensitive", "q": "questionable", "e": "explicit"}
        norm_rating = rating_map.get(raw_rating, "safe")

        try:
            score = int(raw.get("score", 0) or 0)
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
            source=raw.get("source") or "",
            width=int(raw.get("image_width", 0) or 0),
            height=int(raw.get("image_height", 0) or 0),
            created_at=raw.get("created_at") or "",
        )

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
        }
        
        req_params = dict(params or {})
        if self._username and self._api_key:
            req_params["login"] = self._username
            req_params["api_key"] = self._api_key

        status_code = None
        data = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(self._base_url + path, params=req_params) as response:
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
                raise BooruConnectionException(
                    f"Could not connect to {self._base_url} ({exc})"
                ) from exc

        if status_code == 404:
            return {}
        if status_code == 401:
            raise BooruAuthException("Danbooru returned 401 Unauthorized — check username and API key.")
        if status_code == 403:
            raise BooruException("Danbooru 403: Cloudflare check or access denied. Try again or check credentials.")
        if status_code == 422:
            return {}
        if status_code not in (200, 201):
            raise BooruException(f"Danbooru returned status {status_code}")

        return data
