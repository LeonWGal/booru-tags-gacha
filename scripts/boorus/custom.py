"""Universal configurable Custom Booru client."""

import asyncio
from .base import BooruClient, BooruPost
from .danbooru import DanbooruClient
from .moebooru import MoebooruClient
from .gelbooru import GelbooruClient
from .e621 import E621Client
from .philomena import PhilomenaClient


class CustomBooruClient(BooruClient):
    """Wrapper that delegates to the selected engine type with custom credentials and URL."""

    def __init__(
        self,
        engine_type: str = "gelbooru",
        base_url: str = "",
        api_key: str | None = None,
        user_id: str | None = None,
        username: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(base_url, loop=loop)
        self._engine_type = (engine_type or "gelbooru").lower()
        self._delegate = self._create_delegate(base_url, api_key, user_id, username, loop)

    def _create_delegate(
        self,
        base_url: str,
        api_key: str | None,
        user_id: str | None,
        username: str | None,
        loop: asyncio.AbstractEventLoop | None,
    ) -> BooruClient:
        if self._engine_type in ("danbooru", "aibooru"):
            return DanbooruClient(
                base_url=base_url,
                username=username or user_id,
                api_key=api_key,
                loop=loop,
            )
        elif self._engine_type == "moebooru":
            return MoebooruClient(
                base_url=base_url,
                loop=loop,
            )
        elif self._engine_type == "e621":
            return E621Client(
                base_url=base_url,
                username=username or user_id,
                api_key=api_key,
                loop=loop,
            )
        elif self._engine_type == "philomena":
            return PhilomenaClient(
                base_url=base_url,
                api_key=api_key,
                loop=loop,
            )
        else:  # default to gelbooru
            return GelbooruClient(
                base_url=base_url,
                api_key=api_key,
                user_id=user_id,
                loop=loop,
            )

    def image_headers(self, url: str) -> dict[str, str]:
        return self._delegate.image_headers(url)

    async def random_post(
        self,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> BooruPost | None:
        return await self._delegate.random_post(
            tags=tags,
            exclude_tags=exclude_tags,
            rating=rating,
            min_score=min_score,
        )

    async def get_artist_tags(self, tags: list[str]) -> list[str]:
        return await self._delegate.get_artist_tags(tags)
