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


_IMAGE_CACHE: dict[str, Image.Image] = {}


async def fetch_image(url: str, headers: dict[str, str] | None = None) -> Image.Image | None:
    """Download preview/thumbnail image asynchronously with memory caching."""
    if not url:
        return None
    if url in _IMAGE_CACHE:
        return _IMAGE_CACHE[url]

    try:
        req_headers = headers or {
            "User-Agent": (
                "BooruTagsGacha/2.1 (SD-WebUI Extension; +https://github.com)"
            ),
            "Referer": url,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        timeout = aiohttp.ClientTimeout(total=8, connect=4)
        async with aiohttp.ClientSession(timeout=timeout, headers=req_headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    img = Image.open(io.BytesIO(data))
                    img.load()
                    if len(_IMAGE_CACHE) > 150:
                        _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)))
                    _IMAGE_CACHE[url] = img
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
        artist = self.post.tags_artist[0].replace('_', ' ') if self.post.tags_artist else f"#{self.post.id}"
        return f"{self.badge} • {artist}"

    def to_summary_html(self) -> str:
        """Generates a clean HUD status bar with post metadata."""
        dim_str = f"{self.post.width}×{self.post.height}" if self.post.width and self.post.height else ""
        dim_html = f'<span class="gacha-meta-pill">{dim_str}</span>' if dim_str else ""
        fav_html = f'<span class="gacha-meta-pill">Favs: {self.post.fav_count}</span>' if self.post.fav_count > 0 else ""
        tags_count = len(self.post.get_tags())
        tags_html = f'<span class="gacha-meta-pill">{tags_count} tags</span>' if tags_count > 0 else ""

        tier_cls = f"gacha-badge-{self.tier.lower()}"
        rating_cls = f"gacha-rating-{self.post.rating.lower()}"

        return f"""
        <div class="gacha-status-bar">
            <span class="gacha-badge {tier_cls}">
                {self.badge}
            </span>
            <span class="gacha-rating-pill {rating_cls}">
                ● {self.post.rating.upper()}
            </span>
            <span class="gacha-meta-pill">
                Score: {self.post.score}
            </span>
            {fav_html}
            {dim_html}
            {tags_html}
            <a href="{self.post.post_url}" target="_blank" rel="noopener noreferrer" class="gacha-post-link">
                {self.site_name} #{self.post.id} ↗
            </a>
        </div>
        """

    def to_tag_chips_html(self) -> str:
        """Generates categorized interactive tag chips."""
        groups = []

        hint = "Click: Copy | Shift+Click: Add to Include | Alt+Click: Add to Prompt"

        # Artists
        if self.post.tags_artist:
            chips = "".join(f'<span class="gacha-chip gacha-chip-artist" data-tag="{t}" title="{t} ({hint})">{t.replace("_", " ")}</span>' for t in self.post.tags_artist)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label gacha-label-artist">Artists ({len(self.post.tags_artist)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Characters
        if self.post.tags_character:
            chips = "".join(f'<span class="gacha-chip gacha-chip-character" data-tag="{t}" title="{t} ({hint})">{t.replace("_", " ")}</span>' for t in self.post.tags_character)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label gacha-label-character">Characters ({len(self.post.tags_character)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Copyright / Series
        if self.post.tags_copyright:
            chips = "".join(f'<span class="gacha-chip gacha-chip-copyright" data-tag="{t}" title="{t} ({hint})">{t.replace("_", " ")}</span>' for t in self.post.tags_copyright)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label gacha-label-copyright">Series ({len(self.post.tags_copyright)})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # General Tags (top 25)
        if self.post.tags_general:
            top_general = self.post.tags_general[:25]
            chips = "".join(f'<span class="gacha-chip gacha-chip-general" data-tag="{t}" title="{t} ({hint})">{t.replace("_", " ")}</span>' for t in top_general)
            more_lbl = f" (+{len(self.post.tags_general) - 25})" if len(self.post.tags_general) > 25 else ""
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label gacha-label-general">General ({len(top_general)}{more_lbl})</span>
                <div class="gacha-tag-group-items">{chips}</div>
            </div>
            """)

        # Meta Tags
        if self.post.tags_meta:
            chips = "".join(f'<span class="gacha-chip gacha-chip-meta" data-tag="{t}" title="{t} ({hint})">{t.replace("_", " ")}</span>' for t in self.post.tags_meta)
            groups.append(f"""
            <div class="gacha-tag-group">
                <span class="gacha-tag-group-label gacha-label-meta">Meta ({len(self.post.tags_meta)})</span>
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
        badges.append(f'<span class="gacha-badge gacha-badge-ur">UR: {counts["UR"]}</span>')
    if counts["SSR"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-ssr">SSR: {counts["SSR"]}</span>')
    if counts["SR"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-sr">SR: {counts["SR"]}</span>')
    if counts["R"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-r">R: {counts["R"]}</span>')
    if counts["N"] > 0:
        badges.append(f'<span class="gacha-badge gacha-badge-n">N: {counts["N"]}</span>')

    summary_badges = " ".join(badges)
    return f"""
    <div class="gacha-stats-banner">
        <span><strong>Multi-Pull Result ({len(results)}x):</strong></span>
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
    fetch_images: bool = True,
) -> list[GachaPullResult]:
    """Execute 1x, 5x, or 10x Gacha pull with optional image fetching for fast autogacha."""
    fmt_config = config or TagFormatConfig()
    
    include_list = [t.strip() for t in include.split(',') if t.strip()] or None
    exclude_list = [t.strip() for t in exclude.split(',') if t.strip()] or None

    client = get_client(site, custom_cfg=custom_cfg)

    # 1. Fetch candidate posts from client (use batch random_posts for count > 1)
    candidate_posts: list[BooruPost] = []
    try:
        if count == 1:
            single = await client.random_post(
                tags=include_list,
                exclude_tags=exclude_list,
                rating=rating,
                min_score=min_score,
            )
            if single:
                candidate_posts.append(single)
        else:
            candidate_posts = await client.random_posts(
                count=count,
                tags=include_list,
                exclude_tags=exclude_list,
                rating=rating,
                min_score=min_score,
            )
    except Exception as e:
        print(f"[Booru Tags Gacha] Roll error ({site}): {e}")

    # Deduplicate candidates by unique post ID
    unique_candidates: list[BooruPost] = []
    seen_ids: set[str] = set()
    for p in candidate_posts:
        if isinstance(p, BooruPost):
            pid = str(p.id)
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_candidates.append(p)

    # Fallback / Retry: if we didn't get enough unique posts, request more
    if len(unique_candidates) < count:
        retries = 0
        while len(unique_candidates) < count and retries < 2:
            retries += 1
            needed = count - len(unique_candidates)
            try:
                if count == 1:
                    more_p = await client.random_post(
                        tags=include_list,
                        exclude_tags=exclude_list,
                        rating=rating,
                        min_score=min_score,
                    )
                    more_list = [more_p] if more_p else []
                else:
                    more_list = await client.random_posts(
                        count=max(needed * 2, 4),
                        tags=include_list,
                        exclude_tags=exclude_list,
                        rating=rating,
                        min_score=min_score,
                    )
                for p in more_list:
                    if isinstance(p, BooruPost):
                        pid = str(p.id)
                        if pid not in seen_ids:
                            seen_ids.add(pid)
                            unique_candidates.append(p)
                        if len(unique_candidates) >= count:
                            break
            except Exception:
                break

    if not unique_candidates:
        return []

    # 2. Select distinct posts respecting session history
    selected_posts: list[BooruPost] = []

    # First pass: prefer candidates not seen in the current session
    for p in unique_candidates:
        key = (site, str(p.id))
        if key not in _SEEN_POSTS:
            _SEEN_POSTS.add(key)
            selected_posts.append(p)
            if len(selected_posts) >= count:
                break

    # Second pass: if some candidates were previously seen, still fill up to count
    # so that the current batch is ALWAYS filled with distinct posts!
    if len(selected_posts) < count:
        for p in unique_candidates:
            if p not in selected_posts:
                _SEEN_POSTS.add((site, str(p.id)))
                selected_posts.append(p)
                if len(selected_posts) >= count:
                    break

    # Final safeguard: if selected_posts is somehow still empty, fallback to available candidates
    if not selected_posts:
        selected_posts = unique_candidates[:count]

    # Prevent _SEEN_POSTS from accumulating indefinitely
    if len(_SEEN_POSTS) > 1000:
        _SEEN_POSTS.clear()

    # 3. Build card results (skip thumbnail network I/O if fetch_images is False)
    async def _build_card(post: BooruPost) -> GachaPullResult:
        img = None
        if fetch_images:
            img = await fetch_image(post.preview_url, client.image_headers(post.preview_url))
            if not img and post.file_url and post.file_url != post.preview_url:
                img = await fetch_image(post.file_url, client.image_headers(post.file_url))
        return GachaPullResult(post, site, img, fmt_config)

    card_tasks = [_build_card(p) for p in selected_posts]
    results = await asyncio.gather(*card_tasks)

    return list(results)
