"""Favorites and Session History manager for Booru Tags Gacha."""

import json
import os
import threading
import time
from typing import Any

from .base import BooruPost

_EXT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAVORITES_FILE = os.path.join(_EXT_DIR, "gacha_favorites.json")
_FAV_LOCK = threading.RLock()


def load_favorites() -> list[dict[str, Any]]:
    with _FAV_LOCK:
        if not os.path.exists(FAVORITES_FILE):
            return []
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def save_favorites(favs: list[dict[str, Any]]) -> None:
    with _FAV_LOCK:
        try:
            tmp = FAVORITES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(favs, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, FAVORITES_FILE)
        except Exception as e:
            print(f"[Booru Tags Gacha] Could not save favorites: {e}")


def add_favorite(post: BooruPost, site: str, formatted_prompt: str = "") -> bool:
    """Add a post to favorites if not already present."""
    favs = load_favorites()
    fav_id = f"{site}_{post.id}"
    
    for item in favs:
        if item.get("fav_id") == fav_id:
            return False  # Already exists

    tier, badge, star_label = post.rarity

    entry = {
        "fav_id": fav_id,
        "site": site,
        "id": post.id,
        "post_url": post.post_url,
        "preview_url": post.preview_url,
        "rating": post.rating,
        "score": post.score,
        "rarity": badge,
        "star_label": star_label,
        "tags_artist": post.tags_artist,
        "tags_character": post.tags_character,
        "tags_copyright": post.tags_copyright,
        "tags_general": post.tags_general,
        "tags_meta": post.tags_meta,
        "all_tags": post.get_tags(),
        "formatted_prompt": formatted_prompt,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    favs.insert(0, entry)  # Prepend newest
    save_favorites(favs)
    return True


def remove_favorite(fav_id: str) -> bool:
    favs = load_favorites()
    initial_len = len(favs)
    favs = [item for item in favs if item.get("fav_id") != fav_id]
    if len(favs) < initial_len:
        save_favorites(favs)
        return True
    return False


def clear_favorites() -> None:
    save_favorites([])
