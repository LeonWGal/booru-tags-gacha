"""Universal Tag Categorizer for Booru Tags Gacha.
Classifies raw booru tags into Artist, Character, Copyright/Series, General, and Meta categories
using Danbooru batch tag index, Gelbooru/Moebooru APIs, and smart heuristic rules.
"""

import asyncio
import html
import json
import os
from typing import Any
import aiohttp
from .base import normalize_tag

# Global in-memory cache: tag_name -> category (1=artist, 3=copyright, 4=character, 5=meta, 0=general)
_GLOBAL_TAG_CACHE: dict[str, int] = {}
_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tag_cache.json")


def _load_tag_cache() -> None:
    global _GLOBAL_TAG_CACHE
    try:
        if os.path.isfile(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _GLOBAL_TAG_CACHE.update({k: int(v) for k, v in data.items()})
    except Exception:
        pass


def _save_tag_cache() -> None:
    try:
        if _GLOBAL_TAG_CACHE:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_GLOBAL_TAG_CACHE, f, ensure_ascii=False)
    except Exception:
        pass


# Initialize cache from disk
_load_tag_cache()


def register_tag_categories(
    artists: list[str] | None = None,
    characters: list[str] | None = None,
    copyrights: list[str] | None = None,
    generals: list[str] | None = None,
    metas: list[str] | None = None,
) -> None:
    """Seed cache with known categories from a structured post."""
    changed = False
    if artists:
        for t in artists:
            if _GLOBAL_TAG_CACHE.get(t) != 1:
                _GLOBAL_TAG_CACHE[t] = 1
                changed = True
    if characters:
        for t in characters:
            if _GLOBAL_TAG_CACHE.get(t) != 4:
                _GLOBAL_TAG_CACHE[t] = 4
                changed = True
    if copyrights:
        for t in copyrights:
            if _GLOBAL_TAG_CACHE.get(t) != 3:
                _GLOBAL_TAG_CACHE[t] = 3
                changed = True
    if metas:
        for t in metas:
            if _GLOBAL_TAG_CACHE.get(t) != 5:
                _GLOBAL_TAG_CACHE[t] = 5
                changed = True
    if generals:
        for t in generals:
            if t not in _GLOBAL_TAG_CACHE:
                _GLOBAL_TAG_CACHE[t] = 0
                changed = True
    if changed and len(_GLOBAL_TAG_CACHE) % 10 == 0:
        _save_tag_cache()


# Common known metadata tags
KNOWN_META_TAGS = {
    "highres", "absurdres", "superabsurdres", "incredible_absurdres", "lossless",
    "bad_anatomy", "bad_hands", "bad_quality", "lowres", "source_request",
    "check_commentary", "commentary_request", "translated", "third-party_edit",
    "variant_set", "official_art", "concept_art", "character_sheet", "sample",
    "watermark", "signature", "username", "artist_name", "text", "logo",
    "comic", "monochrome", "greyscale", "traditional_media",
}


async def classify_tags(
    tags: list[str],
    site_base_url: str = "",
    api_key: str | None = None,
    user_id: str | None = None,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Classifies a list of tags into (artists, characters, copyrights, generals, metas)."""
    if not tags:
        return [], [], [], [], []

    clean_tags = [html.unescape(t).strip() for t in tags if t.strip()]
    uncached = [t for t in clean_tags if t not in _GLOBAL_TAG_CACHE]

    # 1. Quick heuristic pre-classification
    still_uncached = []
    for t in uncached:
        t_lower = t.lower()
        if t_lower in KNOWN_META_TAGS:
            _GLOBAL_TAG_CACHE[t] = 5
        elif t.endswith("_(cosplay)"):
            _GLOBAL_TAG_CACHE[t] = 4
        else:
            still_uncached.append(t)

    # 2. Query Danbooru global tag database in batch
    if still_uncached:
        await _lookup_danbooru_batch(still_uncached)

    # 3. If site is Gelbooru or Moebooru, query remaining unknown tags from local site API
    remaining_unknown = [t for t in still_uncached if _GLOBAL_TAG_CACHE.get(t, 0) == 0]
    if remaining_unknown and site_base_url:
        if "gelbooru.com" in site_base_url or "rule34" in site_base_url or "safebooru" in site_base_url:
            await _lookup_gelbooru_dapi(remaining_unknown, site_base_url, api_key, user_id)
        elif "yande.re" in site_base_url or "konachan" in site_base_url:
            await _lookup_moebooru_tag(remaining_unknown, site_base_url)

    _save_tag_cache()

    # Build final categorized lists
    artists: list[str] = []
    characters: list[str] = []
    copyrights: list[str] = []
    generals: list[str] = []
    metas: list[str] = []

    for t in clean_tags:
        cat = _GLOBAL_TAG_CACHE.get(t, 0)
        if cat == 1:
            artists.append(t)
        elif cat == 4:
            characters.append(t)
        elif cat == 3:
            copyrights.append(t)
        elif cat in (5, 6):
            metas.append(t)
        else:
            generals.append(t)

    return artists, characters, copyrights, generals, metas


async def _lookup_danbooru_batch(tags: list[str]) -> None:
    """Look up tag categories in Danbooru's master database in batch."""
    try:
        # Danbooru allows search[name_space_delimited]
        names_query = " ".join(tags[:100])
        url = "https://danbooru.donmai.us/tags.json"
        params = {
            "search[name_space_delimited]": names_query,
            "limit": 100,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        for item in data:
                            name = item.get("name")
                            cat = item.get("category", 0)
                            if name:
                                _GLOBAL_TAG_CACHE[name] = int(cat or 0)
    except Exception:
        pass


async def _lookup_gelbooru_dapi(
    tags: list[str],
    base_url: str,
    api_key: str | None = None,
    user_id: str | None = None,
) -> None:
    """Look up tag types from Gelbooru DAPI."""
    try:
        names_query = " ".join(tags[:40])
        url = f"{base_url.rstrip('/')}/index.php"
        params: dict[str, Any] = {
            "page": "dapi",
            "s": "tag",
            "q": "index",
            "names": names_query,
            "json": 1,
        }
        if api_key:
            params["api_key"] = api_key
        if user_id:
            params["user_id"] = user_id

        headers = {
            "User-Agent": "BooruTagsGacha/2.1 (TagClassifier; Stable Diffusion WebUI extension)",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tag_list = data.get("tag") if isinstance(data, dict) else (data if isinstance(data, list) else None)
                    if isinstance(tag_list, list):
                        for t in tag_list:
                            name = t.get("name")
                            ttype = int(t.get("type", 0) or 0)
                            if name:
                                _GLOBAL_TAG_CACHE[name] = ttype
    except Exception:
        pass


async def _lookup_moebooru_tag(tags: list[str], base_url: str) -> None:
    """Look up tag types from Moebooru (Yande.re, Konachan)."""
    if not tags:
        return
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    timeout = aiohttp.ClientTimeout(total=4)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async def fetch_one(tag_name: str):
                try:
                    url = f"{base_url.rstrip('/')}/tag.json"
                    params = {"name": tag_name}
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, list) and data:
                                ttype = int(data[0].get("type", 0) or 0)
                                _GLOBAL_TAG_CACHE[tag_name] = ttype
                except Exception:
                    pass

            # Query up to 35 unknown tags concurrently for high speed
            await asyncio.gather(*[fetch_one(t) for t in tags[:35]])
    except Exception:
        pass
