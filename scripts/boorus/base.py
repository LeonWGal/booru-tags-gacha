"""Core data models, exceptions, and base client for Booru Tags Gacha."""

import asyncio
import html
import aiohttp


def normalize_tag(tag: str) -> str:
    """Canonical form for comparing user-entered tags against booru tags.
    
    Converts spaces and hyphens to underscores, removes leading dashes, unescapes HTML entities, and lowercases.
    """
    if not tag:
        return ""
    t = html.unescape(str(tag)).strip().lstrip('-').lower()
    return t.replace(' ', '_').replace('-', '_')


class BooruException(Exception):
    """Base exception for all booru-related errors."""
    pass


class BooruNotFoundException(BooruException):
    """Raised when no posts match the query."""
    pass


class BooruConnectionException(BooruException):
    """Raised when the site cannot be reached (network/timeout errors)."""
    pass


class BooruAuthException(BooruException):
    """Raised when authentication fails (invalid API key / user ID)."""
    pass


class BooruRateLimitException(BooruException):
    """Raised when rate limited by the booru site."""
    pass


class BooruPost:
    """Normalized representation of a booru post across all engines."""

    def __init__(
        self,
        id: int | str,
        post_url: str,
        file_url: str | None = None,
        preview_url: str | None = None,
        sample_url: str | None = None,
        tags_general: list[str] | None = None,
        tags_character: list[str] | None = None,
        tags_copyright: list[str] | None = None,
        tags_artist: list[str] | None = None,
        tags_meta: list[str] | None = None,
        all_tags: list[str] | None = None,
        rating: str | None = None,
        score: int = 0,
        fav_count: int = 0,
        source: str = "",
        width: int = 0,
        height: int = 0,
        created_at: str = "",
    ):
        self.id = id
        self.post_url = post_url
        self.file_url = file_url or preview_url or ""
        self.preview_url = preview_url or file_url or ""
        self.sample_url = sample_url or file_url or ""
        
        self.tags_general = [html.unescape(t) for t in (tags_general or [])]
        self.tags_character = [html.unescape(t) for t in (tags_character or [])]
        self.tags_copyright = [html.unescape(t) for t in (tags_copyright or [])]
        self.tags_artist = [html.unescape(t) for t in (tags_artist or [])]
        self.tags_meta = [html.unescape(t) for t in (tags_meta or [])]
        
        if all_tags:
            self._all_tags = [html.unescape(t) for t in all_tags]
        else:
            # Combine categories in natural order
            combined = []
            for group in (self.tags_artist, self.tags_character, self.tags_copyright, self.tags_general, self.tags_meta):
                for t in group:
                    if t not in combined:
                        combined.append(t)
            self._all_tags = combined

        # Normalized rating: 'safe', 'sensitive', 'questionable', 'explicit'
        self.rating = self._normalize_rating(rating)
        self.score = score
        self.fav_count = fav_count
        self.source = source
        self.width = width
        self.height = height
        self.created_at = created_at

    @staticmethod
    def _normalize_rating(rating: str | None) -> str:
        if not rating:
            return "safe"
        r = str(rating).lower().strip()
        if r in ("s", "safe", "g", "general"):
            return "safe"
        if r in ("sensitive", "sens"):
            return "sensitive"
        if r in ("q", "questionable"):
            return "questionable"
        if r in ("e", "explicit"):
            return "explicit"
        return "safe"

    @property
    def rarity(self) -> tuple[str, str, str]:
        """Calculates gacha rarity (tier, badge, label) based on score and favorites."""
        metric = max(self.score, self.fav_count * 2)
        if metric >= 150:
            return "UR", "UR", "Ultra Rare"
        elif metric >= 75:
            return "SSR", "SSR", "Super Super Rare"
        elif metric >= 35:
            return "SR", "SR", "Super Rare"
        elif metric >= 10:
            return "R", "R", "Rare"
        else:
            return "N", "N", "Normal"

    def get_tags(self) -> list[str]:
        return list(self._all_tags)

    def to_dict(self) -> dict:
        """Serialize for session storage / favorites."""
        return {
            "id": self.id,
            "post_url": self.post_url,
            "file_url": self.file_url,
            "preview_url": self.preview_url,
            "sample_url": self.sample_url,
            "tags_general": self.tags_general,
            "tags_character": self.tags_character,
            "tags_copyright": self.tags_copyright,
            "tags_artist": self.tags_artist,
            "tags_meta": self.tags_meta,
            "all_tags": self._all_tags,
            "rating": self.rating,
            "score": self.score,
            "fav_count": self.fav_count,
            "source": self.source,
            "width": self.width,
            "height": self.height,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BooruPost":
        return cls(**data)

    def __str__(self) -> str:
        return self.post_url


class BooruClient:
    """Base adapter interface for Booru APIs."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, base_url: str = "", loop: asyncio.AbstractEventLoop | None = None):
        self._base_url = (base_url or "").rstrip('/')
        self._loop = loop

    def image_headers(self, url: str) -> dict[str, str]:
        """Headers used when downloading preview/sample images."""
        return {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Referer": self._base_url or url,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

    async def random_post(
        self,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> BooruPost | None:
        """Fetch a single random post satisfying the criteria."""
        raise NotImplementedError

    async def random_posts(
        self,
        count: int = 1,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        rating: str | None = None,
        min_score: int = 0,
    ) -> list[BooruPost]:
        """Fetch multiple random posts."""
        results = []
        for _ in range(count):
            p = await self.random_post(tags=tags, exclude_tags=exclude_tags, rating=rating, min_score=min_score)
            if p:
                results.append(p)
        return results

    async def get_artist_tags(self, tags: list[str]) -> list[str]:
        """Classify which tags in the list belong to artists."""
        return []
