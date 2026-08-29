"""Multi-Pull Gacha Engine and Card Generator for Booru Tags Gacha."""

import asyncio
import io
from typing import Any
import aiohttp
from PIL import Image

from .base import BooruClient, BooruPost, BooruException, BooruConnectionException
from .formatter import TagFormatConfig, TagFormatter
from . import get_client, SITE_LABEL_BY_KEY


# Global session set of seen posts (site, id)
_SEEN_POSTS: set[tuple[str, str | int]] = set()


def reset_session_history() -> None:
    global _SEEN_POSTS
    _SEEN_POSTS.clear()


async def fetch_image(url: str, headers: dict[str, str] | None = None) -> Image.Image | None:
    """Download preview/thumbnail image asynchronously."""
    if not url:
        return None
    try:
        req_headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": url,
        }
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout, headers=req_headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    img = Image.open(io.BytesIO(data))
                    img.load()
                    return img
    except Exception:
        pass
    return None


class GachaPullResult:
    """Represents a single pulled card result with image and formatted tags."""

    def __init__(
        self,
        post: BooruPost,
        site: str,
        image: Image.Image | None,
        config: TagFormatConfig,
    ):
        self.post = post
        self.site = site
        self.image = image
        self.config = config

        self.full_prompt = TagFormatter.format_post(post, config)
        self.without_artist_prompt = TagFormatter.format_without_artist(post, config)
        self.only_artist_prompt = TagFormatter.format_only_artist(post, config)
        self.only_character_prompt = TagFormatter.format_only_character(post, config)
        self.only_general_prompt = TagFormatter.format_only_general(post, config)
        self.all_raw_prompt = TagFormatter.format_all_raw(post, config)

        self.tier, self.badge, self.star_label = post.rarity
        self.site_name = SITE_LABEL_BY_KEY.get(site, site.capitalize())

    def get_gallery_caption(self) -> str:
        artist = ", ".join(self.post.tags_artist) if self.post.tags_artist else f"#{self.post.id}"
        return f"{self.badge} | ⭐ {self.post.score} | {artist}"

    def to_summary_html(self) -> str:
        """Generates a clean HUD status bar with post metadata."""
        dim_str = f"{self.post.width}×{self.post.height}" if self.post.width and self.post.height else ""
        dim_html = f'<span class="gacha-meta-pill">📐 {dim_str}</span>' if dim_str else ""
        fav_html = f'<span class="gacha-meta-pill">❤️ {self.post.fav_count}</span>' if self.post.fav_count > 0 else ""
        tags_count = len(self.post.get_tags())
        tags_html = f'<span class="gacha-meta-pill">🏷️ {tags_count} tags</span>' if tags_count > 0 else ""

        tier_cls = f"gacha-badge-{self.tier.lower()}"
        rating_cls = f"gacha-rating-{self.post.rating.lower()}"

        return f"""
        <div class="gacha-status-bar">
            <span class="gacha-badge {tier_cls}">
                {self.badge}
            </span>
            <span class="gacha-rating-pill {rating_cls}">
                ● {self.post.rating}
            </span>
            <span class="gacha-meta-pill">
                ⭐ {self.post.score}
            </span>
            {fav_html}
            {dim_html}
            {tags_html}
            <a href="{self.post.post_url}" target="_blank" rel="noopener noreferrer" class="gacha-post-link">
                🔗 {self.site_name} #{self.post.id} ↗
            </a>
        </div>
        """

    def to_tag_chips_html(self) -> str:
        """Generates categorized interactive tag chips."""
        groups = []

        # Artists
        if self.post.tags_artist:
            chips = "".join(f'<span class="gacha-chip gacha-chip-artist">{t}</span>' for t in self.post.tags_artist)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label">🎨 Artists ({len(self.post.tags_artist)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Characters
        if self.post.tags_character:
            chips = "".join(f'<span class="gacha-chip gacha-chip-character">{t}</span>' for t in self.post.tags_character)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label">👤 Characters ({len(self.post.tags_character)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Copyright / Series
        if self.post.tags_copyright:
            chips = "".join(f'<span class="gacha-chip gacha-chip-copyright">{t}</span>' for t in self.post.tags_copyright)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label">📜 Series ({len(self.post.tags_copyright)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Meta Tags
        if self.post.tags_meta:
            chips = "".join(f'<span class="gacha-chip gacha-chip-meta">{t}</span>' for t in self.post.tags_meta)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label">⚙️ Meta ({len(self.post.tags_meta)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        if not groups:
            return ""

        return f'<div class="gacha-tag-chips-wrap">{"".join(groups)}</div>'


def get_multi_pull_stats_html(results: list[GachaPullResult]) -> str:
    """Calculates rarity breakdown for multi-pull rolls."""
    if not results or len(results) <= 1:
        return ""

    counts: dict[str, int] = {"UR": 0, "SSR": 0, "SR": 0, "R": 0, "N": 0}
    for r in results:
        counts[r.tier] = counts.get(r.tier, 0) + 1

    badges = []
    if counts["UR"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-ur">💎 {counts["UR"]}x UR</span>')
    if counts["SSR"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-ssr">🌟 {counts["SSR"]}x SSR</span>')
    if counts["SR"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-sr">✨ {counts["SR"]}x SR</span>')
    if counts["R"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-r">🔷 {counts["R"]}x R</span>')
    if counts["N"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-n">⚪ {counts["N"]}x N</span>')

    summary_badges = " ".join(badges)
    return f"""
    <div class="gacha-stats-banner">
        <span>🎰 <strong>{len(results)}x Multi-Pull Result:</strong></span>
        <div class="gacha-stats-count-group">{summary_badges}</div>
    </div>
    """


async def pull_gacha(
    site: str,
    count: int = 1,
    include: str = "",
    exclude: str = "",
    rating: str = "any",
    min_score: int = 0,
    config: TagFormatConfig | None = None,
    custom_cfg: dict[str, Any] | None = None,
) -> list[GachaPullResult]:
    """Execute 1x, 5x, or 10x Gacha pull."""
    fmt_config = config or TagFormatConfig()
    
    include_list = [t.strip() for t in include.split(',') if t.strip()] or None
    exclude_list = [t.strip() for t in exclude.split(',') if t.strip()] or None

    client = get_client(site, custom_cfg=custom_cfg)

    async def _fetch_single() -> GachaPullResult | None:
        # Re-roll up to 5 times if seen
        for _ in range(5):
            try:
                post = await client.random_post(
                    tags=include_list,
                    exclude_tags=exclude_list,
                    rating=rating,
                    min_score=min_score,
                )
            except Exception as e:
                print(f"[Booru Tags Gacha] Roll error ({site}): {e}")
                return None

            if not post:
                return None

            key = (site, post.id)
            if key not in _SEEN_POSTS or count == 1:
                _SEEN_POSTS.add(key)
                img = await fetch_image(post.preview_url, client.image_headers(post.preview_url))
                if not img and post.file_url != post.preview_url:
                    img = await fetch_image(post.file_url, client.image_headers(post.file_url))
                return GachaPullResult(post, site, img, fmt_config)

        return None

    tasks = [_fetch_single() for _ in range(count)]
    pulled = await asyncio.gather(*tasks)
    
    results = [p for p in pulled if p is not None]
    return results
