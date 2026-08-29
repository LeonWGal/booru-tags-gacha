"""Client for AIBooru (Danbooru-fork for AI generated artwork)."""

import asyncio
from .danbooru import DanbooruClient


class AIBooruClient(DanbooruClient):
    """Client for AIBooru (https://aibooru.online/)."""

    def __init__(
        self,
        base_url: str = "https://aibooru.online/",
        username: str | None = None,
        api_key: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        super().__init__(
            base_url=base_url or "https://aibooru.online/",
            username=username,
            api_key=api_key,
            loop=loop,
        )
