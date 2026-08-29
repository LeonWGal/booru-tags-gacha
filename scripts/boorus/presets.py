"""Presets manager for Booru Tags Gacha."""

import json
import os
import threading
from typing import Any

from . import SITE_DANBOORU, SITE_GELBOORU, SITE_YANDERE, SITE_SAFEBOORU, SITE_E621, SITE_AIBOORU

_EXT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESETS_FILE = os.path.join(_EXT_DIR, "gacha_presets.json")
LEGACY_FILE = os.path.join(_EXT_DIR, "gpr_tabs.json")
_PRESET_LOCK = threading.RLock()


DEFAULT_PRESETS: dict[str, dict[str, Any]] = {
    "🌸 Anime Solo Girl": {
        "site": SITE_DANBOORU,
        "include": "1girl, solo",
        "exclude": "censored, text, watermark, bad anatomy",
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
    },
    "🎨 Masterpiece Artists": {
        "site": SITE_YANDERE,
        "include": "solo",
        "exclude": "bad art, text, logo, lowres",
        "rating": "safe",
        "min_score": 30,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "by",
        "artist_weight": 1.15,
        "max_general_tags": 20,
    },
    "🌆 Cyberpunk & Neon": {
        "site": SITE_DANBOORU,
        "include": "cyberpunk, neon, cityscape",
        "exclude": "monochrome, blurry, text",
        "rating": "safe",
        "min_score": 15,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 25,
    },
    "🏰 Fantasy Scenery": {
        "site": SITE_GELBOORU,
        "include": "scenery, landscape, fantasy",
        "exclude": "monochrome, sketch, comic",
        "rating": "safe",
        "min_score": 10,
        "include_general": True,
        "include_character": False,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 30,
    },
    "🤖 Mecha & Sci-Fi": {
        "site": SITE_DANBOORU,
        "include": "mecha, robot, sci-fi",
        "exclude": "chibi, lowres",
        "rating": "safe",
        "min_score": 10,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 25,
    },
    "🐾 Anthropomorphic (e621)": {
        "site": SITE_E621,
        "include": "solo, anthro",
        "exclude": "feral, gore, text",
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
    },
    "🌟 AI Prompt Explorer (AIBooru)": {
        "site": SITE_AIBOORU,
        "include": "masterpiece, 1girl",
        "exclude": "bad quality, watermark, signature",
        "rating": "any",
        "min_score": 0,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 30,
    },
    "🎲 True Random Chaos": {
        "site": SITE_SAFEBOORU,
        "include": "",
        "exclude": "watermark, text, lowres",
        "rating": "safe",
        "min_score": 0,
        "include_general": True,
        "include_character": True,
        "include_copyright": True,
        "include_artist": True,
        "include_meta": False,
        "artist_format": "raw",
        "artist_weight": 1.1,
        "max_general_tags": 25,
    },
}


def _migrate_legacy_presets() -> dict[str, dict[str, Any]]:
    """Migrate entries from legacy gpr_tabs.json into named presets."""
    if not os.path.exists(LEGACY_FILE):
        return dict(DEFAULT_PRESETS)

    try:
        with open(LEGACY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        presets = dict(DEFAULT_PRESETS)
        
        # Merge txt2img tabs
        txt_tabs = data.get("txt2img", [])
        if isinstance(txt_tabs, list):
            for i, tab in enumerate(txt_tabs):
                if isinstance(tab, dict) and (tab.get("include") or tab.get("exclude")):
                    name = f"Legacy Preset {i + 1}"
                    presets[name] = {
                        "site": tab.get("site", SITE_DANBOORU),
                        "include": tab.get("include", ""),
                        "exclude": tab.get("exclude", ""),
                        "rating": "safe",
                        "min_score": 0,
                        "include_general": True,
                        "include_character": True,
                        "include_copyright": True,
                        "include_artist": True,
                        "include_meta": False,
                        "artist_format": "raw",
                        "artist_weight": 1.1,
                        "max_general_tags": 25,
                    }
        return presets
    except Exception as e:
        print(f"[Booru Tags Gacha] Legacy migration notice: {e}")
        return dict(DEFAULT_PRESETS)


def load_all_presets() -> dict[str, dict[str, Any]]:
    with _PRESET_LOCK:
        if not os.path.exists(PRESETS_FILE):
            presets = _migrate_legacy_presets()
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
    return presets[first_key] if first_key else dict(DEFAULT_PRESETS["🌸 Anime Solo Girl"])


def save_preset(name: str, data: dict[str, Any]) -> None:
    if not name or not name.strip():
        return
    clean_name = name.strip()
    presets = load_all_presets()
    presets[clean_name] = data
    save_all_presets(presets)


def delete_preset(name: str) -> bool:
    presets = load_all_presets()
    if name in presets and len(presets) > 1:
        del presets[name]
        save_all_presets(presets)
        return True
    return False
