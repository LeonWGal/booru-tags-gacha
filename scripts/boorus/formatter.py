"""Advanced Tag Formatter and Prompt Processor for Booru Tags Gacha."""

import html
import random
import re
from typing import Any
from .base import BooruPost, normalize_tag


DEFAULT_EMOTICON_EXCLUSIONS = {
    "0_0", "(o)_(o)", "+_+", "+_-", "._.", "<o>_<o>", "<|>_<|>",
    "=_=", ">_<", "3_3", "6_9", ">_o", "@_@", "^_^", "o_o",
    "u_u", "x_x", "|_|", "||_||", ":3", ";3", "^-^", "-_-",
    "x_o", "o_x", "v_v", "*_*", "t_t", "q_q", ";_;", "d_d",
}


class TagFormatConfig:
    """Configuration options for formatting booru tags into prompts."""

    def __init__(
        self,
        include_general: bool = True,
        include_character: bool = True,
        include_copyright: bool = True,
        include_artist: bool = True,
        include_meta: bool = False,
        replace_underscores: bool = True,
        escape_parentheses: bool = True,
        artist_format: str = "raw",  # 'raw', 'by', 'artist_prefix', 'weighted'
        artist_weight: float = 1.1,
        character_format: str = "raw",  # 'raw', 'weighted'
        character_weight: float = 1.1,
        max_general_tags: int = 0,  # 0 means unlimited
        random_tag_sample: bool = False,
        prefix: str = "",
        suffix: str = "",
        tag_separator: str = ", ",
        blacklist: list[str] | None = None,
        emoticon_exclusions: set[str] | None = None,
    ):
        self.include_general = include_general
        self.include_character = include_character
        self.include_copyright = include_copyright
        self.include_artist = include_artist
        self.include_meta = include_meta
        self.replace_underscores = replace_underscores
        self.escape_parentheses = escape_parentheses
        self.artist_format = artist_format
        self.artist_weight = artist_weight
        self.character_format = character_format
        self.character_weight = character_weight
        self.max_general_tags = max_general_tags
        self.random_tag_sample = random_tag_sample
        self.prefix = prefix
        self.suffix = suffix
        self.tag_separator = tag_separator
        self.blacklist = {normalize_tag(t) for t in (blacklist or []) if t.strip()}
        self.emoticon_exclusions = emoticon_exclusions or DEFAULT_EMOTICON_EXCLUSIONS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TagFormatConfig":
        blacklist = data.get("blacklist", [])
        if isinstance(blacklist, str):
            blacklist = [t.strip() for t in blacklist.split(',') if t.strip()]
        return cls(
            include_general=data.get("include_general", True),
            include_character=data.get("include_character", True),
            include_copyright=data.get("include_copyright", True),
            include_artist=data.get("include_artist", True),
            include_meta=data.get("include_meta", False),
            replace_underscores=data.get("replace_underscores", True),
            escape_parentheses=data.get("escape_parentheses", True),
            artist_format=data.get("artist_format", "raw"),
            artist_weight=float(data.get("artist_weight", 1.1)),
            character_format=data.get("character_format", "raw"),
            character_weight=float(data.get("character_weight", 1.1)),
            max_general_tags=int(data.get("max_general_tags", 0)),
            random_tag_sample=data.get("random_tag_sample", False),
            prefix=data.get("prefix", ""),
            suffix=data.get("suffix", ""),
            tag_separator=data.get("tag_separator", ", "),
            blacklist=blacklist,
        )


class TagFormatter:
    """Processes tags and renders formatted prompt strings."""

    @staticmethod
    def clean_tag(tag: str, config: TagFormatConfig) -> str:
        """Applies HTML entity decoding, underscore replacement and parenthesis escaping to a single tag."""
        if not tag:
            return ""
        
        t = html.unescape(str(tag)).strip()
        
        # Replace underscores if enabled, preserving known emoticons
        if config.replace_underscores:
            if t not in config.emoticon_exclusions:
                t = t.replace('_', ' ')
        
        # Escape parentheses for SD prompt weights if enabled
        if config.escape_parentheses:
            # Avoid double escaping
            t = re.sub(r'(?<!\\)\(', r'\(', t)
            t = re.sub(r'(?<!\\)\)', r'\)', t)
        
        return t

    @classmethod
    def filter_blacklist(cls, tags: list[str], config: TagFormatConfig) -> list[str]:
        """Removes tags present in the blacklist."""
        if not config.blacklist:
            return tags
        return [t for t in tags if normalize_tag(t) not in config.blacklist]

    @classmethod
    def format_artist_tags(cls, artists: list[str], config: TagFormatConfig) -> list[str]:
        """Formats artist tags according to style settings."""
        formatted = []
        for artist in cls.filter_blacklist(artists, config):
            cleaned = cls.clean_tag(artist, config)
            if not cleaned:
                continue
            
            if config.artist_format == "by":
                formatted.append(f"by {cleaned}")
            elif config.artist_format in ("artist_prefix", "artist:"):
                formatted.append(f"artist:{cleaned}")
            elif config.artist_format == "weighted":
                formatted.append(f"({cleaned}:{config.artist_weight:.2f})")
            else:
                formatted.append(cleaned)
        return formatted

    @classmethod
    def format_character_tags(cls, characters: list[str], config: TagFormatConfig) -> list[str]:
        """Formats character tags according to style settings."""
        formatted = []
        for char in cls.filter_blacklist(characters, config):
            cleaned = cls.clean_tag(char, config)
            if not cleaned:
                continue
            
            if config.character_format == "weighted":
                formatted.append(f"({cleaned}:{config.character_weight:.2f})")
            else:
                formatted.append(cleaned)
        return formatted

    @classmethod
    def format_copyright_tags(cls, copyrights: list[str], config: TagFormatConfig) -> list[str]:
        """Formats copyright/series tags."""
        return [
            cls.clean_tag(t, config)
            for t in cls.filter_blacklist(copyrights, config)
            if cls.clean_tag(t, config)
        ]

    @classmethod
    def format_general_tags(cls, generals: list[str], config: TagFormatConfig) -> list[str]:
        """Formats general tags with optional max limit and sampling."""
        filtered = cls.filter_blacklist(generals, config)
        
        if config.max_general_tags > 0 and len(filtered) > config.max_general_tags:
            if config.random_tag_sample:
                filtered = random.sample(filtered, config.max_general_tags)
            else:
                filtered = filtered[:config.max_general_tags]

        return [
            cls.clean_tag(t, config)
            for t in filtered
            if cls.clean_tag(t, config)
        ]

    @classmethod
    def format_meta_tags(cls, metas: list[str], config: TagFormatConfig) -> list[str]:
        """Formats meta tags."""
        return [
            cls.clean_tag(t, config)
            for t in cls.filter_blacklist(metas, config)
            if cls.clean_tag(t, config)
        ]

    @classmethod
    def format_post(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats full post tags based on active category checkboxes."""
        tag_groups = []

        # Artists
        if config.include_artist and post.tags_artist:
            tag_groups.extend(cls.format_artist_tags(post.tags_artist, config))

        # Characters
        if config.include_character and post.tags_character:
            tag_groups.extend(cls.format_character_tags(post.tags_character, config))

        # Copyright / Series
        if config.include_copyright and post.tags_copyright:
            tag_groups.extend(cls.format_copyright_tags(post.tags_copyright, config))

        # General Tags
        if config.include_general and post.tags_general:
            tag_groups.extend(cls.format_general_tags(post.tags_general, config))
        elif config.include_general and not post.tags_general and post.get_tags():
            # Fallback if un-categorized
            tag_groups.extend(cls.format_general_tags(post.get_tags(), config))

        # Meta Tags
        if config.include_meta and post.tags_meta:
            tag_groups.extend(cls.format_meta_tags(post.tags_meta, config))

        # Deduplicate while preserving order
        seen = set()
        unique_tags = []
        for t in tag_groups:
            if t and t not in seen:
                seen.add(t)
                unique_tags.append(t)

        result = config.tag_separator.join(unique_tags)
        if config.prefix and result:
            result = f"{config.prefix.strip()} {result}"
        elif config.prefix:
            result = config.prefix.strip()

        if config.suffix and result:
            result = f"{result} {config.suffix.strip()}"
        elif config.suffix:
            result = config.suffix.strip()

        return result

    @classmethod
    def format_without_artist(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats tags with character, series, general, meta, but EXCLUDING artist [gacha-wa]."""
        tag_groups = []

        if config.include_character and post.tags_character:
            tag_groups.extend(cls.format_character_tags(post.tags_character, config))

        if config.include_copyright and post.tags_copyright:
            tag_groups.extend(cls.format_copyright_tags(post.tags_copyright, config))

        if config.include_general and post.tags_general:
            tag_groups.extend(cls.format_general_tags(post.tags_general, config))
        elif config.include_general and not post.tags_general and post.get_tags():
            # If tags aren't categorized, exclude artist tags from total
            non_artist = [t for t in post.get_tags() if t not in post.tags_artist]
            tag_groups.extend(cls.format_general_tags(non_artist, config))

        if config.include_meta and post.tags_meta:
            tag_groups.extend(cls.format_meta_tags(post.tags_meta, config))

        seen = set()
        unique_tags = []
        for t in tag_groups:
            if t and t not in seen:
                seen.add(t)
                unique_tags.append(t)

        return config.tag_separator.join(unique_tags)

    @classmethod
    def format_only_artist(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats ONLY artist tags [gacha-oa]."""
        if not post.tags_artist:
            return ""
        artists = cls.format_artist_tags(post.tags_artist, config)
        return config.tag_separator.join(artists)

    @classmethod
    def format_only_character(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats ONLY character tags [gacha-oc]."""
        if not post.tags_character:
            return ""
        chars = cls.format_character_tags(post.tags_character, config)
        return config.tag_separator.join(chars)

    @classmethod
    def format_only_general(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats ONLY general tags [gacha-gen]."""
        generals = post.tags_general or post.get_tags()
        if not generals:
            return ""
        return config.tag_separator.join(cls.format_general_tags(generals, config))

    @classmethod
    def format_all_raw(cls, post: BooruPost, config: TagFormatConfig) -> str:
        """Formats ALL tags regardless of category checkboxes [gacha-all]."""
        all_cleaned = [
            cls.clean_tag(t, config)
            for t in cls.filter_blacklist(post.get_tags(), config)
            if cls.clean_tag(t, config)
        ]
        return config.tag_separator.join(all_cleaned)

    @classmethod
    def replace_placeholders(
        cls,
        prompt: str,
        post: BooruPost,
        config: TagFormatConfig,
    ) -> tuple[str, bool]:
        """Replaces placeholders [gacha], [gacha-wa], [gacha-oa], [gacha-oc], [gacha-gen], [gacha-all].
        
        Returns (updated_prompt, was_replaced).
        """
        if not prompt:
            return prompt, False

        placeholders = {
            "[gacha]": lambda: cls.format_post(post, config),
            "[gacha-wa]": lambda: cls.format_without_artist(post, config),
            "[gacha-oa]": lambda: cls.format_only_artist(post, config),
            "[gacha-oc]": lambda: cls.format_only_character(post, config),
            "[gacha-gen]": lambda: cls.format_only_general(post, config),
            "[gacha-all]": lambda: cls.format_all_raw(post, config),
        }

        updated = prompt
        replaced_any = False

        for token, format_fn in placeholders.items():
            if token in updated:
                tag_string = format_fn()
                updated = updated.replace(token, tag_string)
                replaced_any = True

        # Clean up double commas and stray spaces from replacement
        if replaced_any:
            updated = re.sub(r',\s*,+', ', ', updated)
            updated = re.sub(r'^\s*,\s*', '', updated)
            updated = re.sub(r'\s*,\s*$', '', updated)
            updated = re.sub(r'\s+', ' ', updated).strip()

        return updated, replaced_any
