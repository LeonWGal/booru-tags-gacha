"""Presets manager for Booru Tags Gacha."""

import json
import os
import threading
from typing import Any

from . import SITE_DANBOORU, SITE_GELBOORU, SITE_YANDERE, SITE_SAFEBOORU, SITE_E621, SITE_AIBOORU

_EXT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESETS_FILE = os.path.join(_EXT_DIR, "gacha_presets.json")
_PRESET_LOCK = threading.RLock()


DEFAULT_PRESETS: dict[str, dict[str, Any]] = {
    "Character (1girl)": {
        "site": SITE_DANBOORU,
        "include": "1girl, solo",
        "exclude": "loli, shota, ai_generated, bad anatomy, lowres",
        "rating": "safe",
        "min_score": 20,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 25,
        "strip_tags": "text, censored, watermark",
        "strip_tags_enable": True,
    },
    "Scenery (No Humans)": {
        "site": SITE_DANBOORU,
        "include": "scenery, no_humans, landscape",
        "exclude": "1girl, 1boy, character, loli, shota, ai_generated, lowres",
        "rating": "safe",
        "min_score": 15,
        "include_general": True,
        "include_character": False,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 30,
        "strip_tags": "text, censored, watermark",
        "strip_tags_enable": True,
    },
    "NSFW (Explicit)": {
        "site": SITE_GELBOORU,
        "include": "1girl, solo",
        "exclude": "loli, shota, ai_generated, bad anatomy",
        "rating": "explicit",
        "min_score": 15,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 25,
        "strip_tags": "text, censored, watermark",
        "strip_tags_enable": True,
    },
    "Empty": {
        "site": SITE_DANBOORU,
        "include": "",
        "exclude": "loli, shota, ai_generated",
        "rating": "safe",
        "min_score": 0,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.0,
        "max_general_tags": 25,
        "strip_tags": "text, censored, watermark",
        "strip_tags_enable": True,
    },
}


def load_all_presets() -> dict[str, dict[str, Any]]:
    with _PRESET_LOCK:
        if not os.path.exists(PRESETS_FILE):
            presets = dict(DEFAULT_PRESETS)
            save_all_presets(presets)
            return presets
        
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
            return dict(DEFAULT_PRESETS)
        except Exception:
            return dict(DEFAULT_PRESETS)


def save_all_presets(presets: dict[str, dict[str, Any]]) -> None:
    with _PRESET_LOCK:
        try:
            tmp = PRESETS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, PRESETS_FILE)
        except Exception as e:
            print(f"[Booru Tags Gacha] Could not save presets: {e}")


def get_preset_names() -> list[str]:
    presets = load_all_presets()
    return list(presets.keys())


def get_preset(name: str) -> dict[str, Any]:
    presets = load_all_presets()
    if name in presets:
        return presets[name]
    first_key = next(iter(presets.keys()), None)
    return presets[first_key] if first_key else dict(DEFAULT_PRESETS["Character (1girl)"])


def save_preset(name: str, data: dict[str, Any]) -> None:
    if not name or not name.strip():
        return
    clean_name = name.strip()
    presets = load_all_presets()
    presets[clean_name] = data
    save_all_presets(presets)


def auto_save_preset(name: str, data: dict[str, Any]) -> None:
    """Silently auto-saves current preset state."""
    save_preset(name, data)


def delete_preset(name: str) -> bool:
    presets = load_all_presets()
    if name in presets and len(presets) > 1:
        del presets[name]
        save_all_presets(presets)
        return True
    return False
