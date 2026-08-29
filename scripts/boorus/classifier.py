"""Universal Tag Categorizer for Booru Tags Gacha.
Classifies raw booru tags into Artist, Character, Copyright/Series, General, and Meta categories
using Danbooru batch tag index, Gelbooru/Moebooru APIs, and smart heuristic rules.
"""

import asyncio
from typing import Any
import aiohttp
from .base import normalize_tag

# Global in-memory cache: tag_name -> category (1=artist, 3=copyright, 4=character, 5=meta, 0=general)
_GLOBAL_TAG_CACHE: dict[str, int] = {}

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

    clean_tags = [t.strip() for t in tags if t.strip()]
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

    # 2. Query Danbooru global tag database in batch (handles up to 100 tags in a single request)
    if still_uncached:
        await _lookup_danbooru_batch(still_uncached)

    # 3. If site is Gelbooru or Moebooru, query remaining unknown tags from local site API
    remaining_unknown = [t for t in still_uncached if _GLOBAL_TAG_CACHE.get(t, 0) == 0]
    if remaining_unknown and site_base_url:
        if "gelbooru.com" in site_base_url or "rule34" in site_base_url or "safebooru" in site_base_url:
            await _lookup_gelbooru_dapi(remaining_unknown, site_base_url, api_key, user_id)
        elif "yande.re" in site_base_url or "konachan" in site_base_url:
            await _lookup_moebooru_tag(remaining_unknown, site_base_url)

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
            "User-Agent": "BooruTagsGacha/2.1 (TagClassifier; Stable Diffusion WebUI extension)",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)
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
        timeout = aiohttp.ClientTimeout(total=10)
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
    """Look up tag types from Moebooru."""
    try:
        names_query = ",".join(tags[:50])
        url = f"{base_url.rstrip('/')}/tag.json"
        params = {"name": names_query}
        headers = {
            "User-Agent": "BooruTagsGacha/2.1 (TagClassifier; Stable Diffusion WebUI extension)",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        for t in data:
                            name = t.get("name")
                            ttype = int(t.get("type", 0) or 0)
                            if name:
                                _GLOBAL_TAG_CACHE[name] = ttype
    except Exception:
        pass
