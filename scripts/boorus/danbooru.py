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

    _USER_AGENT = "BooruTagsGacha/2.1 (DanbooruClient; SD-WebUI Extension; +https://github.com)"
    _TIMEOUT_SECONDS = 10
    _MAX_RETRIES = 2
    _RETRY_BACKOFF = 0.8

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
            "Referer": "https://danbooru.donmai.us/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

    async def random_posts(
        self,
        count: int = 1,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> list[BooruPost]:
        import random

        include = [normalize_tag(t) for t in (tags or []) if t.strip()]
        excluded = {normalize_tag(t) for t in (exclude_tags or []) if t.strip()}

        rating_map = {"safe": "g", "sensitive": "s", "questionable": "q", "explicit": "e"}
        norm_rating_char = rating_map.get(rating, None) if (rating and rating != "any") else None

        is_authenticated = bool(self._username and self._api_key)

        if is_authenticated:
            # Authenticated users: Danbooru accepts up to 40 tags
            limit = min(max(count * 3, 20), 100)
            query_terms = [f"random:{limit}"]
            if norm_rating_char:
                query_terms.append(f"rating:{norm_rating_char}")
            if min_score > 0:
                query_terms.append(f"score:>={min_score}")
            query_terms.extend(include)
            for ex in excluded:
                query_terms.append(f"-{ex}")

            params = {
                "tags": " ".join(query_terms),
                "limit": limit,
            }
            data = await self._request("/posts.json", params)
            if isinstance(data, list) and data:
                posts = [self._to_post(p) for p in data if isinstance(p, dict) and p.get("id")]
                random.shuffle(posts)
                return posts[:count]
            return []

        # Anonymous users: Danbooru STRICTLY limits queries to MAX 2 tags!
        # Use random:N to get candidate batch quickly without hitting SQL table-scan timeout
        fetch_limit = min(max(count * 4, 30), 100)
        query_terms = [f"random:{fetch_limit}"]
        if include:
            query_terms.append(include[0])
        elif norm_rating_char:
            query_terms.append(f"rating:{norm_rating_char}")
        elif min_score > 0:
            query_terms.append(f"score:>={min_score}")

        params = {
            "tags": " ".join(query_terms),
            "limit": fetch_limit,
        }

        data = await self._request("/posts.json", params)
        if not isinstance(data, list) or not data:
            # Fallback 1: if single post requested, try /posts/random.json
            if count == 1:
                rand_terms = []
                if include:
                    rand_terms.append(include[0])
                if norm_rating_char and len(rand_terms) < 2:
                    rand_terms.append(f"rating:{norm_rating_char}")
                single_data = await self._request("/posts/random.json", {"tags": " ".join(rand_terms)} if rand_terms else None)
                if isinstance(single_data, dict) and single_data.get("id"):
                    return [self._to_post(single_data)]

            # Fallback 2: query without random:N using the first tag directly
            if include:
                data = await self._request("/posts.json", {"tags": include[0], "limit": fetch_limit})

        if not isinstance(data, list) or not data:
            return []

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

        # If strict filtering had fewer than needed, relax score slightly
        if len(candidates) < count:
            for raw in data:
                if raw in candidates or not isinstance(raw, dict) or not raw.get("id"):
                    continue
                post_all_tags = set((raw.get("tag_string") or "").split())
                if excluded and any(normalize_tag(t) in excluded for t in post_all_tags):
                    continue
                candidates.append(raw)

        if not candidates:
            return []

        random.shuffle(candidates)
        return [self._to_post(c) for c in candidates[:count]]

    async def random_post(
        self,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> BooruPost | None:
        posts = await self.random_posts(
            count=1,
            tags=tags,
            exclude_tags=exclude_tags,
            rating=rating,
            min_score=min_score,
        )
        return posts[0] if posts else None

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

        from .classifier import register_tag_categories
        register_tag_categories(
            artists=tags_artist,
            characters=tags_character,
            copyrights=tags_copyright,
            generals=tags_general,
            metas=tags_meta,
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
            "Accept": "application/json, text/plain, */*",
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
                        text = await response.text()
                        if status_code in (200, 201):
                            try:
                                import json
                                data = json.loads(text)
                            except Exception:
                                data = text
                        elif status_code in (404, 422):
                            data = []
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(
                    f"Could not connect to {self._base_url} ({exc})"
                ) from exc

        if status_code in (404, 422):
            return []
        if status_code == 401:
            raise BooruAuthException("Danbooru returned 401 Unauthorized — check username and API key.")
        if status_code == 403:
            raise BooruException("Danbooru 403: Cloudflare check or access denied.")
        if status_code == 429:
            from .base import BooruRateLimitException
            raise BooruRateLimitException("Danbooru 429: Rate limit reached. Please slow down.")
        if status_code not in (200, 201) and status_code is not None:
            raise BooruException(f"Danbooru returned status {status_code}")

        return data
