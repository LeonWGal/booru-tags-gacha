import contextlib
import io
import json
import os
import threading

import aiohttp
import gradio as gr
from PIL import Image
from modules import scripts, shared, script_callbacks

from scripts import boorus
from scripts.boorus import BooruConnectionException, BooruException


EXTENSION_NAME = "Booru Tags Gacha"

# Number of randomizer tabs to render per mode (txt2img / img2img).
NUM_TABS = 5

SITE_LABELS = [label for label, _key in boorus.SITE_CHOICES]
SITE_KEY_BY_LABEL = {label: key for label, key in boorus.SITE_CHOICES}
SITE_LABEL_BY_KEY = {key: label for label, key in boorus.SITE_CHOICES}

# Persist the per-tab Include/Exclude/Site between sessions in a JSON file
# stored at the extension root.
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gpr_tabs.json"
)
_CONFIG_LOCK = threading.RLock()


def _load_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_config(config):
    """Atomic write so concurrent tab saves cannot truncate the file."""
    try:
        tmp_path = _CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _CONFIG_PATH)
    except Exception as e:
        print(f"[{EXTENSION_NAME}] Could not save tab config: {e}")
        try:
            if os.path.exists(_CONFIG_PATH + ".tmp"):
                os.remove(_CONFIG_PATH + ".tmp")
        except Exception:
            pass


def get_saved_tabs(mode):
    """Return a normalized list of NUM_TABS {include, exclude, site} dicts for the mode."""
    with _CONFIG_LOCK:
        tabs = _load_config().get(mode, [])
    result = []
    for i in range(NUM_TABS):
        entry = tabs[i] if i < len(tabs) and isinstance(tabs[i], dict) else {}
        site = entry.get("site", boorus.DEFAULT_SITE)
        if site not in SITE_LABEL_BY_KEY:
            site = boorus.DEFAULT_SITE
        result.append({
            "include": entry.get("include", ""),
            "exclude": entry.get("exclude", ""),
            "site": site,
        })
    return result


def save_tab_field(mode, tab_index, field, value):
    """Persist a single tab's include/exclude/site value, keeping the rest intact."""
    _cancel_debounced_save(mode, tab_index, field)
    with _CONFIG_LOCK:
        config = _load_config()
        tabs = config.get(mode, [])
        if not isinstance(tabs, list):
            tabs = []
        while len(tabs) <= tab_index:
            tabs.append({"include": "", "exclude": "", "site": boorus.DEFAULT_SITE})
        if not isinstance(tabs[tab_index], dict):
            tabs[tab_index] = {"include": "", "exclude": "", "site": boorus.DEFAULT_SITE}
        # Preserve sibling fields if this tab entry was sparse.
        tabs[tab_index].setdefault("include", "")
        tabs[tab_index].setdefault("exclude", "")
        tabs[tab_index].setdefault("site", boorus.DEFAULT_SITE)
        tabs[tab_index][field] = value if value is not None else ""
        config[mode] = tabs
        _save_config(config)


def save_tab_fields(mode, tab_index, site_label, include, exclude):
    """Persist site/include/exclude together (avoids race when Randomize is clicked)."""
    _cancel_debounced_save(mode, tab_index, "include")
    _cancel_debounced_save(mode, tab_index, "exclude")
    with _CONFIG_LOCK:
        config = _load_config()
        tabs = config.get(mode, [])
        if not isinstance(tabs, list):
            tabs = []
        while len(tabs) <= tab_index:
            tabs.append({"include": "", "exclude": "", "site": boorus.DEFAULT_SITE})
        if not isinstance(tabs[tab_index], dict):
            tabs[tab_index] = {"include": "", "exclude": "", "site": boorus.DEFAULT_SITE}
        tabs[tab_index]["site"] = SITE_KEY_BY_LABEL.get(site_label, boorus.DEFAULT_SITE)
        tabs[tab_index]["include"] = include if include is not None else ""
        tabs[tab_index]["exclude"] = exclude if exclude is not None else ""
        config[mode] = tabs
        _save_config(config)


# Debounced text saves: Gradio 4 often skips blur; change fires on every keystroke.
_debounce_timers = {}
_debounce_versions = {}
_debounce_lock = threading.Lock()
_DEBOUNCE_SEC = 0.45


def _cancel_debounced_save(mode, tab_index, field):
    """Invalidate any pending delayed write for this field."""
    key = (mode, tab_index, field)
    with _debounce_lock:
        _debounce_versions[key] = _debounce_versions.get(key, 0) + 1
        timer = _debounce_timers.pop(key, None)
        if timer is not None:
            timer.cancel()


def save_tab_field_debounced(mode, tab_index, field, value):
    key = (mode, tab_index, field)
    with _debounce_lock:
        version = _debounce_versions.get(key, 0) + 1
        _debounce_versions[key] = version

    def _flush():
        with _debounce_lock:
            if _debounce_versions.get(key) != version:
                return
            _debounce_timers.pop(key, None)
        save_tab_field(mode, tab_index, field, value)

    with _debounce_lock:
        existing = _debounce_timers.get(key)
        if existing is not None:
            existing.cancel()
        timer = threading.Timer(_DEBOUNCE_SEC, _flush)
        timer.daemon = True
        _debounce_timers[key] = timer
        timer.start()


async def _fetch_image(url, headers=None):
    if not url:
        return None
    try:
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": url,
            }
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                data = await response.read()
        return Image.open(io.BytesIO(data))
    except Exception:
        return None

# Post IDs already returned during this process ("session"). Keyed by
# (site, post_id) since different sites can reuse the same numeric IDs.
# Used to avoid repeating the same random post. Reset only when the WebUI
# is restarted, and never persisted to disk.
_seen_post_ids = set()

# How many times to re-roll a random post when it has already been seen before
# giving up and returning a duplicate (e.g. when the tag pool is exhausted).
_MAX_DEDUP_ATTEMPTS = 8


async def get_random_tags(site, include, exclude):
    if not boorus.site_credentials_ok(site):
        site_label = SITE_LABEL_BY_KEY.get(site, site)
        if site == boorus.SITE_CUSTOM:
            msg = f"Set a base URL for the Custom site in Settings → {EXTENSION_NAME}"
        else:
            msg = f"Configure the API key / user ID for {site_label} in Settings → {EXTENSION_NAME}"
        return msg, None, msg, ""

    # Split on commas only: tags may contain spaces ("ai generated"), which
    # the site clients convert to underscores themselves.
    include_list = [t.strip() for t in include.split(',') if t.strip()] or None
    exclude_list = [t.strip() for t in exclude.split(',') if t.strip()] or None

    blacklist_raw = getattr(shared.opts, "gpr_universalBlacklist", "") or ""
    blacklist = [t.strip() for t in blacklist_raw.split(',') if t.strip()]
    if blacklist:
        exclude_list = (exclude_list or []) + blacklist

    client = boorus.get_client(site)

    try:
        # Re-roll until we get a post we haven't shown this session, or until we
        # run out of attempts (small tag pools may have no unseen posts left).
        post = None
        for _ in range(_MAX_DEDUP_ATTEMPTS):
            post = await client.random_post(tags=include_list, exclude_tags=exclude_list)
            if not post or (site, post.id) not in _seen_post_ids:
                break
    except BooruConnectionException as e:
        print(f"[{EXTENSION_NAME}] Connection error: {e}")
        msg = "Could not connect (network/timeout). Check your internet connection and try again."
        return msg, None, msg, ""
    except BooruException as e:
        print(f"[{EXTENSION_NAME}] Booru error: {e}")
        return str(e), None, str(e), ""
    except Exception as e:
        print(f"[{EXTENSION_NAME}] Unexpected error: {e}")
        msg = f"Unexpected error: {e}"
        return msg, None, msg, ""

    if not post:
        msg = "Couldn't find a post with the specified tags"
        return msg, None, msg, ""

    # Remember this post so it isn't returned again this session.
    _seen_post_ids.add((site, post.id))

    # Strip excluded tags (per-tab Exclude + universal blacklist) from the
    # returned list too: sites match posts, not individual tags, so a post
    # can legitimately match the search yet still carry an unwanted tag
    # under a variant spelling (e.g. "ai-generated" vs "ai_generated").
    tags = post.get_tags()
    if exclude_list:
        excluded_set = {boorus.normalize_tag(t) for t in exclude_list}
        tags = [t for t in tags if boorus.normalize_tag(t) not in excluded_set]

    # Some sites (e.g. Danbooru) already expose artist tags on the post; for
    # others we look them up separately. Non-fatal: a failed lookup just
    # means no separate artist field.
    artist_tags = [t for t in post.artist_tags if t in tags]
    if not artist_tags:
        try:
            artist_tags = await client.get_artist_tags(tags)
        except Exception as e:
            print(f"[{EXTENSION_NAME}] Could not fetch tag types: {e}")
            artist_tags = []

    replace_underscores = getattr(shared.opts, "gpr_replaceUnderscores", True)
    exclusion_list = getattr(shared.opts, "gpr_undersocreReplacementExclusionList", "").split(',')

    def _format(tag):
        if not replace_underscores or tag in exclusion_list:
            return tag
        return tag.replace("_", " ")

    # Artist tags stay in the main tag list and are also exposed separately.
    display_tags = [_format(t) for t in tags]
    artist_display = [_format(t) for t in artist_tags]

    image = await _fetch_image(post.file_url, client.image_headers(post.file_url))

    return ', '.join(display_tags), image, str(post), ', '.join(artist_display)


async def randomize_with_history(site_label, include, exclude, history, index):
    """Fetch a new random post and, on success, append it to the navigation history."""
    site = SITE_KEY_BY_LABEL.get(site_label, boorus.DEFAULT_SITE)
    tags, image, url, artist = await get_random_tags(site, include, exclude)

    if image is not None:
        # Drop any "forward" entries if the user had navigated back, then append.
        history = history[:index + 1] if index >= 0 else []
        history = history + [(tags, image, url, artist)]
        index = len(history) - 1

    return tags, image, url, artist, history, index


def _show_history_entry(history, index):
    tags, image, url, artist = history[index]
    return tags, image, url, artist, history, index


def go_previous(history, index):
    """Show the previous image in the history, if any."""
    if history and index > 0:
        return _show_history_entry(history, index - 1)
    return gr.update(), gr.update(), gr.update(), gr.update(), history, index


def go_next(history, index):
    """Show the next image in the history, if any."""
    if history and index < len(history) - 1:
        return _show_history_entry(history, index + 1)
    return gr.update(), gr.update(), gr.update(), gr.update(), history, index


def clear_all():
    """Reset the displayed result and the navigation history."""
    return None, None, None, None, [], -1


class GPRScript(scripts.Script):

    # Render this script's UI inside the "sampler" section, just above the
    # "Sampling method" dropdown (ScriptSampler, sorting_priority 0). A negative
    # sorting_priority guarantees we are placed before it, i.e. directly under
    # the TIPO panel and above Sampling method.
    section = "sampler"
    sorting_priority = -100

    def __init__(self) -> None:
        super().__init__()

    def title(self):
        return EXTENSION_NAME

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def _build_tab(self, is_img2img, mode, tab_index, defaults):
        """Build a single randomizer tab and wire up all of its events.

        Returns the list of components created so the caller can register them.
        """
        prompt_component = self.text2img if not is_img2img else self.img2img

        # Navigation history: list of (tags, image, url, artist) and the index
        # of the entry currently shown.
        history_state = gr.State([])
        index_state = gr.State(-1)

        site_dropdown = gr.Dropdown(
            label='Site',
            choices=SITE_LABELS,
            value=SITE_LABEL_BY_KEY.get(defaults.get("site", boorus.DEFAULT_SITE), SITE_LABELS[0]),
        )

        include_tags_textbox = gr.Textbox(label='Include Tags', value=defaults.get("include", ""), placeholder="es: 1girl, blue_hair, solo")
        exclude_tags_textbox = gr.Textbox(label='Exclude Tags', value=defaults.get("exclude", ""), placeholder="es: nsfw, text, watermark")

        with gr.Row():
            send_text_button = gr.Button(value='Randomize', variant='primary', size='sm')
            cancel_button = gr.Button(value='Cancel', variant='stop', size='sm')
            clear_button = gr.Button(value='Clear', size='sm')

        result_tags_textbox = gr.Textbox(label='Tags', show_copy_button=True, interactive=False)

        artist_tags_textbox = gr.Textbox(label='Artist', show_copy_button=True, interactive=False)

        with gr.Row():
            replace_tags_button = gr.Button(value='Replace Tags', variant='primary', size='sm')
            append_tags_button = gr.Button(value='Append Tags', size='sm')

        preview_image = gr.Image(interactive=False, show_label=False, height=400)

        with gr.Row():
            prev_button = gr.Button(value='◀ Previous', size='sm')
            next_button = gr.Button(value='Next ▶', size='sm')

        url_textbox = gr.Textbox(label='Post URL', show_copy_button=True, interactive=False)

        # Persist Site/Include/Exclude between sessions.
        # Gradio 4 often does not fire Textbox.blur reliably; use change (debounced)
        # and also snapshot all three fields when Randomize runs.
        site_dropdown.change(
            fn=lambda v, m=mode, i=tab_index: save_tab_field(
                m, i, "site", SITE_KEY_BY_LABEL.get(v, boorus.DEFAULT_SITE)
            ),
            inputs=site_dropdown,
            outputs=[],
            queue=False,
            show_progress=False,
        )
        include_tags_textbox.change(
            fn=lambda v, m=mode, i=tab_index: save_tab_field_debounced(m, i, "include", v),
            inputs=include_tags_textbox,
            outputs=[],
            queue=False,
            show_progress=False,
        )
        exclude_tags_textbox.change(
            fn=lambda v, m=mode, i=tab_index: save_tab_field_debounced(m, i, "exclude", v),
            inputs=exclude_tags_textbox,
            outputs=[],
            queue=False,
            show_progress=False,
        )
        # Fallback blur (when Gradio delivers it).
        include_tags_textbox.blur(
            fn=lambda v, m=mode, i=tab_index: save_tab_field(m, i, "include", v),
            inputs=include_tags_textbox,
            outputs=[],
            queue=False,
            show_progress=False,
        )
        exclude_tags_textbox.blur(
            fn=lambda v, m=mode, i=tab_index: save_tab_field(m, i, "exclude", v),
            inputs=exclude_tags_textbox,
            outputs=[],
            queue=False,
            show_progress=False,
        )

        with contextlib.suppress(AttributeError):
            replace_tags_button.click(fn=lambda result_tags:(result_tags), inputs=result_tags_textbox, outputs=prompt_component)
            append_tags_button.click(fn=lambda result_tags, tags:(f"{tags}, {result_tags}"), inputs=[result_tags_textbox, prompt_component], outputs=prompt_component)

        async def _randomize_and_persist(site_label, include, exclude, history, index, m=mode, i=tab_index):
            save_tab_fields(m, i, site_label, include, exclude)
            return await randomize_with_history(site_label, include, exclude, history, index)

        randomize_event = send_text_button.click(
            fn=_randomize_and_persist,
            inputs=[site_dropdown, include_tags_textbox, exclude_tags_textbox, history_state, index_state],
            outputs=[result_tags_textbox, preview_image, url_textbox, artist_tags_textbox, history_state, index_state],
        )

        cancel_button.click(fn=None, inputs=None, outputs=None, cancels=[randomize_event])

        prev_button.click(
            fn=go_previous,
            inputs=[history_state, index_state],
            outputs=[result_tags_textbox, preview_image, url_textbox, artist_tags_textbox, history_state, index_state],
        )
        next_button.click(
            fn=go_next,
            inputs=[history_state, index_state],
            outputs=[result_tags_textbox, preview_image, url_textbox, artist_tags_textbox, history_state, index_state],
        )

        clear_button.click(
            fn=clear_all,
            inputs=None,
            outputs=[preview_image, url_textbox, result_tags_textbox, artist_tags_textbox, history_state, index_state],
        )

        return [site_dropdown, include_tags_textbox, exclude_tags_textbox, send_text_button, clear_button, result_tags_textbox, replace_tags_button, append_tags_button, preview_image, url_textbox, artist_tags_textbox, prev_button, next_button, cancel_button]

    def ui(self, is_img2img):
        mode = "img2img" if is_img2img else "txt2img"
        saved_tabs = get_saved_tabs(mode)

        components = []
        with gr.Accordion(EXTENSION_NAME, open=False):
            with gr.Tabs():
                for tab_index in range(NUM_TABS):
                    with gr.Tab(f"Tab {tab_index + 1}"):
                        components.extend(
                            self._build_tab(is_img2img, mode, tab_index, saved_tabs[tab_index])
                        )

        return components

    def on_ui_settings():
        GPR_SECTION = ("gpr", EXTENSION_NAME)

        gpr_options = {
            "gpr_api_key": shared.OptionInfo("", "Gelbooru api_key", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_user_id": shared.OptionInfo("", "Gelbooru user_id", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_rule34_api_key": shared.OptionInfo("", "Rule34 api_key", gr.Textbox).info("<a href=\"https://rule34.xxx/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_rule34_user_id": shared.OptionInfo("", "Rule34 user_id", gr.Textbox).info("<a href=\"https://rule34.xxx/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_danbooru_username": shared.OptionInfo("", "Danbooru username", gr.Textbox).info("Your account's login name (not the numeric user ID). Required together with the API key — one without the other is ignored."),
            "gpr_danbooru_api_key": shared.OptionInfo("", "Danbooru api_key", gr.Textbox).info("<a href=\"https://danbooru.donmai.us/profile\" target=\"_blank\">Profile → API Key</a>. Danbooru is behind Cloudflare and may reject automated requests (403) even with valid credentials."),
            "gpr_e621_username": shared.OptionInfo("", "e621 username", gr.Textbox).info("Optional. Required together with the API key — one without the other is ignored."),
            "gpr_e621_api_key": shared.OptionInfo("", "e621 api_key", gr.Textbox).info("Optional. <a href=\"https://e621.net/users/home\" target=\"_blank\">Account → Manage API Access</a>. Without credentials e621 hides some posts via its default blacklist."),
            "gpr_custom_base_url": shared.OptionInfo("", "Custom site base URL", gr.Textbox).info("Base URL of any Gelbooru-DAPI-compatible booru (e.g. https://tbib.org/), used by the 'Custom' site option."),
            "gpr_custom_api_key": shared.OptionInfo("", "Custom site api_key", gr.Textbox),
            "gpr_custom_user_id": shared.OptionInfo("", "Custom site user_id", gr.Textbox),
            # Taken from a1111-sd-webui-tagcomplete
            "gpr_replaceUnderscores": shared.OptionInfo(True, "Replace underscores with spaces on insertion"),
            "gpr_undersocreReplacementExclusionList": shared.OptionInfo("0_0,(o)_(o),+_+,+_-,._.,<o>_<o>,<|>_<|>,=_=,>_<,3_3,6_9,>_o,@_@,^_^,o_o,u_u,x_x,|_|,||_||", "Underscore replacement exclusion list").info("Add tags that shouldn't have underscores replaced with spaces, separated by comma."),
            "gpr_universalBlacklist": shared.OptionInfo("", "Universal tag blacklist").info("Tags listed here are always excluded from results and stripped from the returned tag list, in addition to the per-run Exclude Tags. Separate with commas (e.g. nsfw, text, watermark)."),
        }

        for key, opt, in gpr_options.items():
            opt.section = GPR_SECTION
            shared.opts.add_option(key, opt)

    script_callbacks.on_ui_settings(on_ui_settings)

    def after_component(self, component, **kwargs):
        if kwargs.get("elem_id") == "txt2img_prompt":
            self.text2img = component

        if kwargs.get("elem_id") == "img2img_prompt":
            self.img2img = component
