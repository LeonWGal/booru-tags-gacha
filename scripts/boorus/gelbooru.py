"""Client for Gelbooru-DAPI compatible boorus (Gelbooru, Rule34, Safebooru, TBIB)."""

import asyncio
import html
import json
from random import randint
from typing import Any
import xml.etree.ElementTree as ET
import aiohttp

from .base import (
    BooruClient,
    BooruConnectionException,
    BooruException,
    BooruAuthException,
    BooruPost,
    normalize_tag,
)
from .classifier import classify_tags


def _parse_xml_to_dict(xml_str: str) -> dict[str, Any]:
    """Parse XML string to dictionary using standard library ElementTree."""
    try:
        root = ET.fromstring(xml_str)
        posts_list = []
        for elem in root.findall("post"):
            posts_list.append(elem.attrib)
        
        count = root.attrib.get("count", "0")
        return {
            "posts": {
                "@count": count,
                "post": posts_list,
            },
            "@attributes": {
                "count": count,
            },
            "post": posts_list,
        }
    except Exception:
        return {}


class GelbooruClient(BooruClient):
    """Modern JSON & XML DAPI client for Gelbooru, Rule34, Safebooru, TBIB, etc."""

    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    _TIMEOUT_SECONDS = 15
    _MAX_RETRIES = 2
    _RETRY_BACKOFF = 1.0

    def __init__(
        self,
        base_url: str = "https://gelbooru.com/",
        api_key: str | None = None,
        user_id: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(base_url, loop=loop)
        self._api_key = api_key.strip() if api_key else None
        self._user_id = user_id.strip() if user_id else None
        self._tag_cache: dict[str, int] = {}

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
            if rating == "safe":
                query_terms.append("rating:general")
            elif rating == "sensitive":
                query_terms.append("rating:sensitive")
            elif rating == "questionable":
                query_terms.append("rating:questionable")
            elif rating == "explicit":
                query_terms.append("rating:explicit")

        if min_score > 0:
            query_terms.append(f"score:>={min_score}")

        query_terms.extend(include)
        query_terms.extend(excluded)

        # 1. Query count via standard DAPI XML endpoint (returns accurate total count on Gelbooru, Rule34, Safebooru)
        count_params: dict[str, Any] = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "limit": 1,
        }
        if self._api_key:
            count_params["api_key"] = self._api_key
        if self._user_id:
            count_params["user_id"] = self._user_id

        if query_terms:
            count_params["tags"] = ' '.join(query_terms)

        count_payload = await self._request(count_params)
        count = self._extract_count(count_payload)

        # 2. Fetch random post using safe pid page offset
        limit = 20
        page_params = dict(count_params)
        page_params["limit"] = limit
        page_params["json"] = 1

        if count > limit:
            max_pid = min(max(0, (count // limit) - 1), 100)
            page_params["pid"] = randint(0, max_pid)
        else:
            page_params["pid"] = 0

        post_payload = await self._request(page_params)
        raw_post = self._extract_first_post(post_payload)

        if not raw_post:
            # Fallback without json parameter (XML format)
            del page_params["json"]
            xml_payload = await self._request(page_params)
            raw_post = self._extract_first_post(xml_payload)

        if not raw_post and page_params.get("pid", 0) > 0:
            # Fallback to page 0 if deep page was empty
            page_params["pid"] = 0
            post_payload = await self._request(page_params)
            raw_post = self._extract_first_post(post_payload)

        if not raw_post:
            return None

        return await self._to_post(raw_post)

    def _extract_count(self, payload: Any) -> int:
        if isinstance(payload, dict):
            attrs = payload.get("@attributes") or {}
            if "count" in attrs:
                try:
                    return int(attrs["count"])
                except (TypeError, ValueError):
                    pass
            posts_node = payload.get("posts") or {}
            if "@count" in posts_node:
                try:
                    return int(posts_node["@count"])
                except (TypeError, ValueError):
                    pass
            if "post" in payload and isinstance(payload["post"], list):
                return len(payload["post"])
        elif isinstance(payload, list):
            return len(payload)
        return 0

    def _extract_first_post(self, payload: Any) -> dict[str, Any] | None:
        import random
        if isinstance(payload, list) and payload:
            valid = [p for p in payload if isinstance(p, dict) and p.get("id")]
            return random.choice(valid) if valid else None
        if isinstance(payload, dict):
            if "post" in payload:
                posts = payload["post"]
                if isinstance(posts, list) and posts:
                    valid = [p for p in posts if isinstance(p, dict) and p.get("id")]
                    return random.choice(valid) if valid else None
                if isinstance(posts, dict) and posts.get("id"):
                    return posts
            if "posts" in payload:
                posts = payload["posts"].get("post")
                if isinstance(posts, list) and posts:
                    valid = [p for p in posts if isinstance(p, dict) and p.get("id")]
                    return random.choice(valid) if valid else None
                if isinstance(posts, dict) and posts.get("id"):
                    return posts
        return None

    async def _to_post(self, raw: dict[str, Any]) -> BooruPost:
        raw = {k.lstrip('@'): v for k, v in raw.items()}
        post_id = str(raw.get("id", ""))
        web_base = self._base_url.replace("api.rule34.xxx", "rule34.xxx").rstrip('/')
        post_url = f"{web_base}/index.php?page=post&s=view&id={post_id}"

        file_url = raw.get("file_url") or ""
        if not file_url and raw.get("image") and raw.get("directory"):
            file_url = f"https://img3.gelbooru.com/images/{raw['directory']}/{raw['image']}"
        preview_url = raw.get("preview_url") or file_url
        sample_url = raw.get("sample_url") or file_url

        tags_raw = html.unescape(str(raw.get("tags", ""))).strip()
        all_tags = [html.unescape(t) for t in tags_raw.split()] if tags_raw else []

        raw_rating = str(raw.get("rating", "general")).lower()
        rating_map = {
            "g": "safe", "general": "safe", "safe": "safe",
            "s": "sensitive", "sensitive": "sensitive",
            "q": "questionable", "questionable": "questionable",
            "e": "explicit", "explicit": "explicit",
        }
        norm_rating = rating_map.get(raw_rating, "safe")

        try:
            score = int(raw.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0

        # Categorize tags with Universal Tag Classifier
        artists, characters, copyrights, generals, metas = await classify_tags(
            all_tags,
            site_base_url=self._base_url,
            api_key=self._api_key,
            user_id=self._user_id,
        )

        return BooruPost(
            id=post_id,
            post_url=post_url,
            file_url=file_url,
            preview_url=preview_url,
            sample_url=sample_url,
            tags_general=generals,
            tags_character=characters,
            tags_copyright=copyrights,
            tags_artist=artists,
            tags_meta=metas,
            all_tags=all_tags,
            rating=norm_rating,
            score=score,
            fav_count=0,
            source=raw.get("source") or "",
            width=int(raw.get("width", 0) or 0),
            height=int(raw.get("height", 0) or 0),
            created_at=str(raw.get("created_at") or ""),
        )

    async def _request(self, params: dict[str, Any]) -> Any:
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {
            "User-Agent": self._USER_AGENT,
            "Referer": self._base_url,
            "Accept": "application/json, text/xml, application/xml, */*",
        }

        url = f"{self._base_url}/index.php"

        status_code = None
        data = None

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(url, params=params) as response:
                        status_code = response.status
                        text = await response.text()
                        
                        # Try JSON first
                        try:
                            data = json.loads(text)
                        except Exception:
                            # Fallback to XML with standard library ElementTree
                            try:
                                data = _parse_xml_to_dict(text)
                            except Exception:
                                data = text
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(f"Could not connect to {self._base_url} ({exc})") from exc

        if status_code == 401:
            raise BooruAuthException("Gelbooru DAPI: 401 Unauthorized — check API Key and User ID in Settings.")
        if status_code == 403:
            raise BooruException("Gelbooru DAPI: 403 Forbidden.")
        if status_code not in (200, 201):
            raise BooruException(f"Gelbooru DAPI returned status {status_code}")

        return data
