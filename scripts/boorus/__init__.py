"""Booru Tags Gacha engines registry and factory."""

from typing import Any

from .base import (
    BooruClient,
    BooruPost,
    BooruException,
    BooruNotFoundException,
    BooruConnectionException,
    BooruAuthException,
    BooruRateLimitException,
    normalize_tag,
)
from .danbooru import DanbooruClient
from .aibooru import AIBooruClient
from .moebooru import MoebooruClient
from .gelbooru import GelbooruClient
from .e621 import E621Client
from .philomena import PhilomenaClient
from .custom import CustomBooruClient

SITE_DANBOORU = "danbooru"
SITE_GELBOORU = "gelbooru"
SITE_YANDERE = "yandere"
SITE_KONACHAN = "konachan"
SITE_SAFEBOORU = "safebooru"
SITE_RULE34 = "rule34"
SITE_AIBOORU = "aibooru"
SITE_E621 = "e621"
SITE_E926 = "e926"
SITE_DERPIBOORU = "derpibooru"
SITE_CUSTOM = "custom"

DEFAULT_SITE = SITE_DANBOORU

SITE_CHOICES: list[tuple[str, str]] = [
    ("Danbooru", SITE_DANBOORU),
    ("Gelbooru", SITE_GELBOORU),
    ("Yande.re (Moebooru)", SITE_YANDERE),
    ("Konachan", SITE_KONACHAN),
    ("Safebooru", SITE_SAFEBOORU),
    ("Rule34", SITE_RULE34),
    ("AIBooru (AI Art)", SITE_AIBOORU),
    ("e621", SITE_E621),
    ("e926 (SFW e621)", SITE_E926),
    ("Derpibooru", SITE_DERPIBOORU),
    ("Custom Booru", SITE_CUSTOM),
]

SITE_LABEL_BY_KEY = {key: label for label, key in SITE_CHOICES}
SITE_KEY_BY_LABEL = {label: key for label, key in SITE_CHOICES}


def _get_opt(name: str, default: Any = "") -> Any:
    try:
        from modules import shared
        return getattr(shared.opts, name, default) or default
    except Exception:
        return default


def site_credentials_ok(site: str) -> bool:
    """Validate whether required credentials are set for the site."""
    if site == SITE_GELBOORU:
        return bool(_get_opt("gpr_api_key")) and bool(_get_opt("gpr_user_id"))
    if site == SITE_RULE34:
        return bool(_get_opt("gpr_rule34_api_key")) and bool(_get_opt("gpr_rule34_user_id"))
    if site == SITE_CUSTOM:
        return bool(_get_opt("gpr_custom_base_url"))
    return True


def get_client(site: str, custom_cfg: dict[str, Any] | None = None) -> BooruClient:
    """Factory function returning the corresponding BooruClient."""
    if site == SITE_DANBOORU:
        return DanbooruClient(
            base_url="https://danbooru.donmai.us/",
            username=_get_opt("gpr_danbooru_username"),
            api_key=_get_opt("gpr_danbooru_api_key"),
        )
    elif site == SITE_AIBOORU:
        return AIBooruClient(
            base_url="https://aibooru.online/",
            username=_get_opt("gpr_aibooru_username"),
            api_key=_get_opt("gpr_aibooru_api_key"),
        )
    elif site == SITE_YANDERE:
        return MoebooruClient(
            base_url="https://yande.re/",
        )
    elif site == SITE_KONACHAN:
        return MoebooruClient(
            base_url="https://konachan.net/",
        )
    elif site == SITE_GELBOORU:
        return GelbooruClient(
            base_url="https://gelbooru.com/",
            api_key=_get_opt("gpr_api_key"),
            user_id=_get_opt("gpr_user_id"),
        )
    elif site == SITE_RULE34:
        return GelbooruClient(
            base_url="https://api.rule34.xxx/",
            api_key=_get_opt("gpr_rule34_api_key"),
            user_id=_get_opt("gpr_rule34_user_id"),
        )
    elif site == SITE_SAFEBOORU:
        return GelbooruClient(
            base_url="https://safebooru.org/",
        )
    elif site == SITE_E621:
        return E621Client(
            base_url="https://e621.net/",
            username=_get_opt("gpr_e621_username"),
            api_key=_get_opt("gpr_e621_api_key"),
        )
    elif site == SITE_E926:
        return E621Client(
            base_url="https://e926.net/",
            username=_get_opt("gpr_e621_username"),
            api_key=_get_opt("gpr_e621_api_key"),
        )
    elif site == SITE_DERPIBOORU:
        return PhilomenaClient(
            base_url="https://derpibooru.org/",
            api_key=_get_opt("gpr_derpibooru_api_key"),
        )
    elif site == SITE_CUSTOM:
        cfg = custom_cfg or {}
        return CustomBooruClient(
            engine_type=cfg.get("engine") or _get_opt("gpr_custom_engine", "gelbooru"),
            base_url=cfg.get("base_url") or _get_opt("gpr_custom_base_url", "https://tbib.org/"),
            api_key=cfg.get("api_key") or _get_opt("gpr_custom_api_key"),
            user_id=cfg.get("user_id") or _get_opt("gpr_custom_user_id"),
            username=cfg.get("username") or _get_opt("gpr_custom_username"),
        )
    
    # Fallback to Danbooru
    return DanbooruClient()
