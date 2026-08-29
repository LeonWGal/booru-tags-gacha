"""Client for Philomena-based boorus (Derpibooru, Ponybooru)."""

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


class PhilomenaClient(BooruClient):
    """Client for Derpibooru and Philomena engine boorus."""

    _USER_AGENT = "BooruTagsGacha/2.0 (Stable Diffusion WebUI extension)"
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 1.5

    def __init__(
        self,
        base_url: str = "https://derpibooru.org/",
        api_key: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(base_url, loop=loop)
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

        query_terms = []
        if rating and rating != "any":
            query_terms.append(rating)

        if min_score > 0:
            query_terms.append(f"score.gte:{min_score}")

        query_terms.extend(include)
        query_terms.extend(excluded)

        q_str = ', '.join(query_terms) if query_terms else "*"

        params: dict[str, Any] = {
            "q": q_str,
            "sf": "random",
            "per_page": 1,
        }
        if self._api_key:
            params["key"] = self._api_key

        data = await self._request("/api/v1/json/search/posts", params)
        posts = data.get("posts") if isinstance(data, dict) else None
        if not posts or not isinstance(posts, list):
            return None

        return self._to_post(posts[0])

    def _to_post(self, raw: dict[str, Any]) -> BooruPost:
        post_id = raw.get("id", "")
        reps = raw.get("representations") or {}
        file_url = reps.get("full") or raw.get("view_url") or ""
        preview_url = reps.get("medium") or reps.get("thumb") or file_url
        sample_url = reps.get("large") or reps.get("medium") or file_url

        all_tags = raw.get("tags") or []
        tags_artist = []
        tags_character = []
        tags_copyright = []
        tags_general = []
        tags_meta = []

        for t in all_tags:
            t_str = str(t)
            if t_str.startswith("artist:"):
                tags_artist.append(t_str[7:])
            elif t_str.startswith("oc:") or t_str.startswith("character:"):
                tags_character.append(t_str.split(":", 1)[1])
            elif t_str.startswith("spoiler:") or t_str in ("safe", "suggestive", "questionable", "explicit"):
                tags_meta.append(t_str)
            else:
                tags_general.append(t_str)

        raw_rating = "safe"
        if "explicit" in all_tags:
            raw_rating = "explicit"
        elif "questionable" in all_tags:
            raw_rating = "questionable"
        elif "suggestive" in all_tags:
            raw_rating = "sensitive"

        try:
            score = int(raw.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0

        try:
            fav_count = int(raw.get("faves", 0) or 0)
        except (TypeError, ValueError):
            fav_count = 0

        post_url = f"{self._base_url}/images/{post_id}"

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
            rating=raw_rating,
            score=score,
            fav_count=fav_count,
            source=str(raw.get("source_url") or ""),
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

        if status_code not in (200, 201):
            raise BooruException(f"Philomena returned status {status_code}")

        return data
