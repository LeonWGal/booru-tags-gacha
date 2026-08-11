from modules import shared

from .base import BooruClient, BooruConnectionException, BooruException, BooruNotFoundException, BooruPost, normalize_tag
from .dapi import DapiClient
from .danbooru import DanbooruClient
from .e621 import E621Client

SITE_GELBOORU = "gelbooru"
SITE_RULE34 = "rule34"
SITE_SAFEBOORU = "safebooru"
SITE_DANBOORU = "danbooru"
SITE_E621 = "e621"
SITE_CUSTOM = "custom"

DEFAULT_SITE = SITE_GELBOORU

# (display label, site key) pairs, in the order shown in the dropdown.
SITE_CHOICES = [
    ("Gelbooru", SITE_GELBOORU),
    ("Rule34", SITE_RULE34),
    ("Safebooru", SITE_SAFEBOORU),
    ("Danbooru", SITE_DANBOORU),
    ("e621", SITE_E621),
    ("Custom (Gelbooru-compatible)", SITE_CUSTOM),
]

# Sites where random_post() requires an API key / user ID to work at all.
SITES_REQUIRING_CREDENTIALS = {SITE_GELBOORU, SITE_RULE34}


def _opt(name, default=""):
    return getattr(shared.opts, name, default) or default


def site_credentials_ok(site):
    if site == SITE_GELBOORU:
        return bool(_opt("gpr_api_key")) and bool(_opt("gpr_user_id"))
    if site == SITE_RULE34:
        return bool(_opt("gpr_rule34_api_key")) and bool(_opt("gpr_rule34_user_id"))
    if site == SITE_CUSTOM:
        return bool(_opt("gpr_custom_base_url"))
    return True


def get_client(site):
    if site == SITE_GELBOORU:
        return DapiClient("https://gelbooru.com/", api_key=_opt("gpr_api_key"), user_id=_opt("gpr_user_id"))
    if site == SITE_RULE34:
        return DapiClient("https://api.rule34.xxx/", api_key=_opt("gpr_rule34_api_key"), user_id=_opt("gpr_rule34_user_id"))
    if site == SITE_SAFEBOORU:
        return DapiClient("https://safebooru.org/")
    if site == SITE_DANBOORU:
        return DanbooruClient(
            "https://danbooru.donmai.us/",
            username=_opt("gpr_danbooru_username"),
            api_key=_opt("gpr_danbooru_api_key"),
        )
    if site == SITE_E621:
        return E621Client(
            "https://e621.net/",
            username=_opt("gpr_e621_username"),
            api_key=_opt("gpr_e621_api_key"),
        )
    if site == SITE_CUSTOM:
        return DapiClient(
            _opt("gpr_custom_base_url"),
            api_key=_opt("gpr_custom_api_key"),
            user_id=_opt("gpr_custom_user_id"),
        )
    raise ValueError(f"Unknown booru site: {site}")
