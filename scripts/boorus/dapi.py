"""Client for any Gelbooru-DAPI-compatible booru (Gelbooru, Rule34, Safebooru, ...).

Originally based on PyGelbooru (https://pypi.org/project/pygelbooru/), generalized
to work against any site that speaks the same index.php?page=dapi&s=post&q=index
XML API by simply pointing it at a different base URL.
"""
import asyncio
import xml.parsers.expat
from random import randint

import aiohttp
import xmltodict
from furl import furl

from .base import BooruClient, BooruConnectionException, BooruException, BooruPost


class DapiClient(BooruClient):
    def __init__(self, base_url, api_key=None, user_id=None, loop=None):
        self._base_url = base_url
        self._api_key = api_key
        self._user_id = user_id
        self._loop = loop

    async def random_post(self, tags=None, exclude_tags=None):
        formatted = self._format_tags(tags, exclude_tags)

        endpoint = self._endpoint('post')
        endpoint.args['limit'] = 1
        if formatted:
            endpoint.args['tags'] = ' '.join(formatted)

        payload = self._parse_xml(await self._request(str(endpoint)))
        posts_node = payload.get('posts') or {}

        count = int(posts_node.get('@count', 0) or 0)
        if not count:
            return None

        # pid is a 0-based page index, so the last valid page is count - 1.
        # Gelbooru also refuses to paginate deeper than 20000 results.
        offset = randint(0, max(min(count, 20000) - 1, 0))
        return await self._fetch_one(formatted, offset)

    async def _fetch_one(self, formatted_tags, page):
        endpoint = self._endpoint('post')
        endpoint.args['limit'] = 1
        endpoint.args['pid'] = page
        if formatted_tags:
            endpoint.args['tags'] = ' '.join(formatted_tags)

        payload = self._parse_xml(await self._request(str(endpoint)))
        posts_node = payload.get('posts') or {}
        raw = posts_node.get('post')
        if not raw:
            return None

        raw = raw[0] if isinstance(raw, list) else raw
        return self._to_post(raw)

    # Some DAPI-compatible sites (e.g. Safebooru) silently ignore the plural
    # "names=" bulk-lookup parameter and return an unrelated broad tag list
    # instead of an error, so exact lookups must go through "name=" one tag
    # at a time. Concurrency is capped to avoid hammering the site.
    _TAG_LOOKUP_CONCURRENCY = 5

    async def get_artist_tags(self, tags):
        if not tags:
            return []

        semaphore = asyncio.Semaphore(self._TAG_LOOKUP_CONCURRENCY)

        async def _lookup(tag_name):
            async with semaphore:
                endpoint = self._endpoint('tag')
                endpoint.args['name'] = tag_name
                try:
                    payload = self._parse_xml(await self._request(str(endpoint)))
                except BooruException:
                    return None

            tags_node = payload.get('tags') or {}
            raw = tags_node.get('tag')
            if not raw:
                return None
            raw = raw[0] if isinstance(raw, list) else raw
            raw = {k.strip('@'): v for k, v in raw.items()}
            try:
                tag_type = int(raw.get('type', 0) or 0)
            except (TypeError, ValueError):
                tag_type = 0
            # Gelbooru tag types: 0=general, 1=artist, 3=copyright, 4=character, 5=metadata
            return tag_name if tag_type == 1 else None

        results = await asyncio.gather(*(_lookup(t) for t in tags))
        return [t for t in results if t]

    def _to_post(self, raw):
        raw = {k.strip('@'): v for k, v in raw.items()}
        post_id = int(raw.get('id', 0) or 0)
        file_url = raw.get('file_url')
        tags = str(raw.get('tags', '')).split()
        rating = raw.get('rating')
        try:
            score = int(raw.get('score', 0) or 0)
        except (TypeError, ValueError):
            score = 0
        post_url = f"{self._base_url.rstrip('/')}/index.php?page=post&s=view&id={post_id}"
        return BooruPost(post_id, file_url, tags, post_url, rating=rating, score=score)

    def _endpoint(self, s):
        endpoint = furl(self._base_url)
        endpoint.args['page'] = 'dapi'
        endpoint.args['s'] = s
        endpoint.args['q'] = 'index'
        if self._api_key:
            endpoint.args['api_key'] = self._api_key
        if self._user_id:
            endpoint.args['user_id'] = self._user_id
        return endpoint

    def _format_tags(self, tags, exclude_tags):
        tags = [t.strip().lower().replace(' ', '_') for t in tags] if tags else []
        exclude_tags = ['-' + t.strip().lstrip('-').lower().replace(' ', '_') for t in exclude_tags] if exclude_tags else []
        return tags + exclude_tags

    def _parse_xml(self, payload):
        try:
            data = xmltodict.parse(payload)
        except xml.parsers.expat.ExpatError:
            raise BooruException("The site returned a malformed response")
        return {k.strip('@'): v for k, v in data.items()}

    # Networking knobs
    _TIMEOUT_SECONDS = 20
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 2  # seconds, multiplied by attempt number

    async def _request(self, url):
        timeout = aiohttp.ClientTimeout(total=self._TIMEOUT_SECONDS)
        headers = {"User-Agent": "Mozilla/5.0", "Referer": self._base_url}

        status_code, data = None, None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(loop=self._loop, timeout=timeout, headers=headers) as session:
                    async with session.get(url) as response:
                        status_code = response.status
                        data = await response.read()
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF * attempt)
                    continue
                raise BooruConnectionException(
                    f"Could not connect to {self._base_url} after {self._MAX_RETRIES} attempts: {exc}"
                ) from exc

        if status_code == 401:
            raise BooruException("The site returned 401 — check the API key / user ID in Settings")
        elif status_code == 403:
            raise BooruException("The site returned 403 (access denied)")
        elif status_code not in (200, 201):
            raise BooruException(f"The site returned a non-200 status code: {status_code}")

        return data
