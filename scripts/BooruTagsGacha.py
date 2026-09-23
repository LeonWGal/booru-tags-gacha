"""Booru Tags Gacha - Modern Extension for SD WebUI & Forge Neo (Gradio 4+).
Adaptive Solid Native Gradio Styling & Lobe Theme Glassmorphism Support.
"""

import asyncio
import contextlib
import os
import re
from typing import Any

import gradio as gr
from PIL import Image

from modules import scripts, shared, script_callbacks
from scripts import boorus
from scripts.boorus import (
    SITE_CHOICES,
    SITE_LABEL_BY_KEY,
    SITE_KEY_BY_LABEL,
    DEFAULT_SITE,
    BooruPost,
    BooruException,
    BooruConnectionException,
    BooruAuthException,
)
from scripts.boorus.formatter import TagFormatConfig, TagFormatter
from scripts.boorus.gacha import pull_gacha, GachaPullResult, get_multi_pull_stats_html
from scripts.boorus import presets, favorites

EXTENSION_NAME = "Booru Tags Gacha"


def _run_async(coro):
    """Run an async coroutine from synchronous script methods."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        return loop.run_until_complete(coro)
    except Exception:
        new_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


class BooruTagsGachaScript(scripts.Script):
    section = "sampler"
    sorting_priority = -100

    def __init__(self) -> None:
        super().__init__()
        self.txt2img_prompt = None
        self.txt2img_neg_prompt = None
        self.img2img_prompt = None
        self.img2img_neg_prompt = None

    def title(self):
        return EXTENSION_NAME

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        mode = "img2img" if is_img2img else "txt2img"
        all_preset_names = presets.get_preset_names()
        default_preset_name = all_preset_names[0] if all_preset_names else "Character (1girl)"
        current_preset = presets.get_preset(default_preset_name)

        # Internal state for multi-card gacha and history
        gacha_results_state = gr.State([])
        active_card_idx_state = gr.State(0)
        history_state = gr.State([])
        history_idx_state = gr.State(-1)

        with gr.Accordion(EXTENSION_NAME, open=False, elem_classes=["booru-gacha-container"]):
            # Top Preset Manager Bar
            with gr.Row(equal_height=True):
                preset_dropdown = gr.Dropdown(
                    label="Preset",
                    choices=all_preset_names,
                    value=default_preset_name,
                    scale=4,
                )
                save_preset_btn = gr.Button("Save", size="sm", scale=1)
                new_preset_btn = gr.Button("New", size="sm", scale=1)
                del_preset_btn = gr.Button("Delete", size="sm", scale=1)

            # Search & Filter Controls
            with gr.Row():
                site_dropdown = gr.Dropdown(
                    label="Site",
                    choices=[label for label, _ in SITE_CHOICES],
                    value=SITE_LABEL_BY_KEY.get(current_preset.get("site", DEFAULT_SITE), "Danbooru"),
                    scale=2,
                )
                rating_dropdown = gr.Dropdown(
                    label="Rating",
                    choices=["any", "safe", "sensitive", "questionable", "explicit"],
                    value=current_preset.get("rating", "safe"),
                    scale=1,
                )
                min_score_number = gr.Number(
                    label="Min Score",
                    value=current_preset.get("min_score", 0),
                    precision=0,
                    scale=1,
                )

            with gr.Row():
                include_tags_box = gr.Textbox(
                    label="Include Tags",
                    value=current_preset.get("include", ""),
                    placeholder="e.g.: 1girl, solo, blue_hair, scenic",
                    scale=1,
                )
                exclude_tags_box = gr.Textbox(
                    label="Exclude Tags",
                    value=current_preset.get("exclude", ""),
                    placeholder="e.g.: censored, text, watermark, bad anatomy",
                    scale=1,
                )

            # Gacha Pull Buttons
            with gr.Row():
                pull_1x_btn = gr.Button("Roll 1x", elem_classes=["gacha-pull-btn", "gacha-pull-btn-1x"])
                pull_5x_btn = gr.Button("Lucky 5x", elem_classes=["gacha-pull-btn", "gacha-pull-btn-5x"])
                pull_10x_btn = gr.Button("Multi 10x (SSR)", elem_classes=["gacha-pull-btn", "gacha-pull-btn-10x"])
                cancel_pull_btn = gr.Button("Cancel", elem_classes=["gacha-pull-btn", "gacha-pull-btn-cancel"])

            # Multi-Pull Stats Banner & Selected HUD
            stats_banner_html = gr.HTML(value="", elem_classes=["gacha-stats-wrap"])
            status_html = gr.HTML(value="")
            
            # Preview and Gallery Grid
            with gr.Row(elem_classes=["gacha-preview-gallery-row"]):
                with gr.Column(scale=1, min_width=220, elem_classes=["gacha-preview-col"]):
                    preview_image = gr.Image(
                        label="Selected Preview",
                        interactive=False,
                        height=380,
                        show_label=False,
                        show_download_button=False,
                        show_share_button=False,
                        elem_classes=["gacha-preview-image"],
                    )
                with gr.Column(scale=2, min_width=300, elem_classes=["gacha-gallery-col"]):
                    gacha_gallery = gr.Gallery(
                        label="Gacha Multi-Pull Cards",
                        show_label=False,
                        elem_id="booru_gacha_gallery",
                        elem_classes=["gacha-gallery-grid"],
                        columns=[2, 3, 4],
                        height=380,
                        object_fit="contain",
                        preview=False,
                        allow_preview=False,
                        show_download_button=False,
                        show_share_button=False,
                    )

            # Categorized Tag Chips Inspector
            tag_chips_html = gr.HTML(value="", elem_classes=["gacha-tag-chips-container"])

            # Formatted Prompt Output
            with gr.Row():
                full_tags_textbox = gr.Textbox(
                    label="Formatted Prompt Tags",
                    placeholder="Rolled tags will appear here...",
                    show_copy_button=True,
                    lines=3,
                    scale=3,
                )

            with gr.Row():
                artist_tags_box = gr.Textbox(label="Artist", show_copy_button=True, scale=1)
                character_tags_box = gr.Textbox(label="Character", show_copy_button=True, scale=1)
                copyright_tags_box = gr.Textbox(label="Series / Copyright", show_copy_button=True, scale=1)

            # Quick Prompt Actions
            with gr.Row():
                insert_gacha_btn = gr.Button("⚡ Insert [gacha] to Prompt", variant="primary", elem_classes=["gacha-action-btn", "gacha-gacha-btn"])
                replace_prompt_btn = gr.Button("Replace Prompt", elem_classes=["gacha-action-btn", "gacha-insert-btn"])
                append_prompt_btn = gr.Button("Append Prompt", elem_classes=["gacha-action-btn", "gacha-insert-btn"])
                prepend_prompt_btn = gr.Button("Prepend Prompt", elem_classes=["gacha-action-btn", "gacha-insert-btn"])
                add_negative_btn = gr.Button("To Negative", elem_classes=["gacha-action-btn", "gacha-insert-btn", "gacha-neg-btn"])

            with gr.Row():
                insert_artist_btn = gr.Button("Insert Artist", size="sm", elem_classes=["gacha-sub-btn"])
                insert_character_btn = gr.Button("Insert Character", size="sm", elem_classes=["gacha-sub-btn"])
                fav_post_btn = gr.Button("Save to Favorites", size="sm", elem_classes=["gacha-sub-btn", "gacha-fav-btn"])

            # History & Navigation Row
            with gr.Row():
                prev_btn = gr.Button("Previous", size="sm", elem_classes=["gacha-sub-btn"])
                next_btn = gr.Button("Next", size="sm", elem_classes=["gacha-sub-btn"])
                clear_btn = gr.Button("Clear", size="sm", elem_classes=["gacha-sub-btn"])

            # Primary Auto-Gacha Controls (Prominently placed, remembered across sessions)
            with gr.Row(elem_classes=["gacha-autogacha-controls-row"]):
                auto_gacha_chk = gr.Checkbox(
                    label="⚡ Auto-Gacha on Generate (Unique random card for every image in batch)",
                    value=bool(getattr(shared.opts, "gpr_auto_gacha_enable", False)),
                    scale=2,
                )
                auto_mode_dropdown = gr.Dropdown(
                    label="Auto-Gacha Mode",
                    choices=[
                        "Replace Full Prompt",
                        "Replace [gacha...] placeholders",
                        "Append to Prompt",
                        "Prepend to Prompt",
                    ],
                    value=str(getattr(shared.opts, "gpr_auto_gacha_mode", "Replace Full Prompt")),
                    scale=2,
                )
                auto_neg_chk = gr.Checkbox(label="Auto-Add Exclude to Negative", value=False, scale=1)

            # Built-in Favorites Browser Section
            def _safe_get_fav_choices():
                try:
                    return [
                        f"[{f.get('rarity', 'R')}] #{f.get('id')} ({f.get('site')}) - {', '.join(f.get('tags_artist', []) or ['unknown'])}"
                        for f in favorites.load_favorites()
                    ]
                except Exception:
                    return []

            with gr.Accordion("Favorites Explorer", open=False):
                fav_list_choices = _safe_get_fav_choices()
                with gr.Row():
                    fav_dropdown = gr.Dropdown(
                        label="Saved Cards",
                        choices=fav_list_choices,
                        value=fav_list_choices[0] if fav_list_choices else None,
                        scale=3,
                    )
                    fav_load_btn = gr.Button("Load to Prompt", size="sm", scale=1)
                    fav_del_btn = gr.Button("Delete Favorite", size="sm", scale=1)
                    fav_clear_all_btn = gr.Button("Clear All", size="sm", scale=1)

            # Collapsible Advanced Formatting Configuration
            with gr.Accordion("Advanced Tag Formatting", open=False):
                with gr.Row():
                    inc_general_chk = gr.Checkbox(label="General Tags", value=current_preset.get("include_general", True))
                    inc_char_chk = gr.Checkbox(label="Character Tags", value=current_preset.get("include_character", True))
                    inc_copy_chk = gr.Checkbox(label="Series / Copyright", value=current_preset.get("include_copyright", True))
                    inc_artist_chk = gr.Checkbox(label="Artist Tags", value=current_preset.get("include_artist", True))
                    inc_meta_chk = gr.Checkbox(label="Meta Tags", value=current_preset.get("include_meta", False))

                with gr.Row():
                    replace_underscores_chk = gr.Checkbox(label="Replace _ with Space (Preserve Emoticons)", value=True)
                    escape_parens_chk = gr.Checkbox(label=r"Escape Parentheses \( \)", value=True)
                    artist_fmt_dropdown = gr.Dropdown(
                        label="Artist Format",
                        choices=["raw", "by", "artist_prefix", "weighted"],
                        value=current_preset.get("artist_format", "raw"),
                    )
                    artist_weight_slider = gr.Slider(
                        label="Artist Weight (if weighted)",
                        minimum=0.5,
                        maximum=2.0,
                        step=0.05,
                        value=current_preset.get("artist_weight", 1.1),
                    )

                with gr.Row():
                    max_tags_slider = gr.Slider(
                        label="Max General Tags (0 = All)",
                        minimum=0,
                        maximum=60,
                        step=1,
                        value=current_preset.get("max_general_tags", 25),
                    )
                    tag_prefix_box = gr.Textbox(label="Prompt Prefix", placeholder="e.g. masterpiece, best quality,")
                    tag_suffix_box = gr.Textbox(label="Prompt Suffix", placeholder="e.g. highres, absurdres")

                with gr.Row():
                    strip_tags_box = gr.Textbox(
                        label="Strip Tags from Prompt",
                        placeholder="e.g. loli, shota, ai generated",
                        value=current_preset.get("strip_tags", "loli, shota, ai generated"),
                        scale=3,
                    )
                    strip_tags_chk = gr.Checkbox(
                        label="Enable Tag Stripping",
                        value=current_preset.get("strip_tags_enable", True),
                        scale=1,
                    )

            # Placeholders Guide Accordion
            with gr.Accordion("Auto-Gacha Placeholders Reference", open=False):
                gr.Markdown(
                    "You can insert placeholders into your txt2img/img2img prompt:\n"
                    "- `[gacha]`: Full formatted tags for the rolled card\n"
                    "- `[gacha-wa]`: Tags without artist (character, series, general, meta)\n"
                    "- `[gacha-oa]`: Artist tags only\n"
                    "- `[gacha-oc]`: Character tags only\n"
                    "- `[gacha-gen]`: General tags only\n"
                    "- `[gacha-all]`: All raw tags without filtering\n\n"
                    "*Tip: Click `⚡ Insert [gacha] to Prompt` to instantly set up multi-batch random rolls.*"
                )

        # Helper to construct TagFormatConfig from UI values
        def _get_format_config(
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix,
            strip_tags="loli, shota, ai generated", strip_tags_enable=True
        ):
            blacklist_raw = getattr(shared.opts, "gpr_universalBlacklist", "") or ""
            bl_list = [t.strip() for t in blacklist_raw.split(',') if t.strip()]
            return TagFormatConfig(
                include_general=inc_gen,
                include_character=inc_char,
                include_copyright=inc_copy,
                include_artist=inc_art,
                include_meta=inc_meta,
                replace_underscores=rep_under,
                escape_parentheses=esc_par,
                artist_format=art_fmt,
                artist_weight=art_wt,
                max_general_tags=int(max_tags),
                prefix=prefix,
                suffix=suffix,
                blacklist=bl_list,
                strip_tags=strip_tags,
                strip_tags_enable=bool(strip_tags_enable),
            )

        # Event: Preset Selection Change
        def _on_preset_change(preset_name):
            p = presets.get_preset(preset_name)
            site_key = p.get("site", DEFAULT_SITE)
            site_lbl = SITE_LABEL_BY_KEY.get(site_key, "Danbooru")
            return (
                site_lbl,
                p.get("rating", "safe"),
                p.get("min_score", 0),
                p.get("include", ""),
                p.get("exclude", ""),
                p.get("include_general", True),
                p.get("include_character", True),
                p.get("include_copyright", True),
                p.get("include_artist", True),
                p.get("include_meta", False),
                p.get("artist_format", "raw"),
                p.get("artist_weight", 1.1),
                p.get("max_general_tags", 25),
                p.get("strip_tags", "loli, shota, ai generated"),
                p.get("strip_tags_enable", True),
            )

        preset_dropdown.change(
            fn=_on_preset_change,
            inputs=[preset_dropdown],
            outputs=[
                site_dropdown, rating_dropdown, min_score_number,
                include_tags_box, exclude_tags_box,
                inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
                artist_fmt_dropdown, artist_weight_slider, max_tags_slider,
                strip_tags_box, strip_tags_chk,
            ],
            show_progress="hidden",
        )

        # Helper: Auto-save preset settings
        def _auto_save_active(
            preset_name, site_lbl, rating_val, score_val, inc_val, exc_val,
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            art_fmt, art_wt, max_tags, strip_tags="loli, shota, ai generated", strip_tags_enable=True
        ):
            if not preset_name:
                return
            site_k = SITE_KEY_BY_LABEL.get(site_lbl, DEFAULT_SITE)
            data = {
                "site": site_k,
                "rating": rating_val,
                "min_score": int(score_val) if score_val is not None else 0,
                "include": inc_val or "",
                "exclude": exc_val or "",
                "include_general": bool(inc_gen),
                "include_character": bool(inc_char),
                "include_copyright": bool(inc_copy),
                "include_artist": bool(inc_art),
                "include_meta": bool(inc_meta),
                "artist_format": art_fmt or "raw",
                "artist_weight": float(art_wt) if art_wt is not None else 1.1,
                "max_general_tags": int(max_tags) if max_tags is not None else 25,
                "strip_tags": strip_tags or "",
                "strip_tags_enable": bool(strip_tags_enable),
            }
            presets.auto_save_preset(preset_name, data)

        auto_save_inputs = [
            preset_dropdown, site_dropdown, rating_dropdown, min_score_number,
            include_tags_box, exclude_tags_box,
            inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
            artist_fmt_dropdown, artist_weight_slider, max_tags_slider,
            strip_tags_box, strip_tags_chk,
        ]

        include_tags_box.blur(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        exclude_tags_box.blur(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        site_dropdown.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        rating_dropdown.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        min_score_number.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        inc_general_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        inc_char_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        inc_copy_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        inc_artist_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        inc_meta_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        artist_fmt_dropdown.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        artist_weight_slider.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        max_tags_slider.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        strip_tags_box.blur(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")
        strip_tags_chk.change(fn=_auto_save_active, inputs=auto_save_inputs, outputs=None, show_progress="hidden")

        # Event: Save Preset
        def _on_save_preset(
            preset_name, site_lbl, rating_val, score_val, inc_val, exc_val,
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            art_fmt, art_wt, max_tags, strip_tags, strip_tags_enable
        ):
            _auto_save_active(
                preset_name, site_lbl, rating_val, score_val, inc_val, exc_val,
                inc_gen, inc_char, inc_copy, inc_art, inc_meta,
                art_fmt, art_wt, max_tags, strip_tags, strip_tags_enable
            )
            all_names = presets.get_preset_names()
            gr.Info(f"Preset '{preset_name}' saved")
            return gr.Dropdown(choices=all_names, value=preset_name)

        save_preset_btn.click(
            fn=_on_save_preset,
            inputs=[
                preset_dropdown, site_dropdown, rating_dropdown, min_score_number,
                include_tags_box, exclude_tags_box,
                inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
                artist_fmt_dropdown, artist_weight_slider, max_tags_slider,
                strip_tags_box, strip_tags_chk,
            ],
            outputs=[preset_dropdown],
        )

        # Event: New Preset
        def _on_new_preset(current_name):
            all_names = presets.get_preset_names()
            new_name = f"Custom Preset {len(all_names) + 1}"
            presets.save_preset(new_name, presets.get_preset(current_name))
            updated_names = presets.get_preset_names()
            gr.Info(f"Created preset '{new_name}'")
            return gr.Dropdown(choices=updated_names, value=new_name)

        new_preset_btn.click(
            fn=_on_new_preset,
            inputs=[preset_dropdown],
            outputs=[preset_dropdown],
        )

        # Event: Delete Preset
        def _on_del_preset(preset_name):
            deleted = presets.delete_preset(preset_name)
            updated_names = presets.get_preset_names()
            if deleted:
                gr.Info(f"Deleted preset '{preset_name}'")
            return gr.Dropdown(choices=updated_names, value=updated_names[0])

        del_preset_btn.click(
            fn=_on_del_preset,
            inputs=[preset_dropdown],
            outputs=[preset_dropdown],
        )

        # Main Gacha Execution Function
        async def _do_gacha_pull(
            count, preset_name, site_lbl, rating_val, min_score_val, inc_tags, exc_tags,
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix,
            strip_tags, strip_tags_enable,
            history, history_idx,
        ):
            # Auto-save current preset state on roll
            _auto_save_active(
                preset_name, site_lbl, rating_val, min_score_val, inc_tags, exc_tags,
                inc_gen, inc_char, inc_copy, inc_art, inc_meta,
                art_fmt, art_wt, max_tags, strip_tags, strip_tags_enable
            )

            site_key = SITE_KEY_BY_LABEL.get(site_lbl, DEFAULT_SITE)
            fmt_config = _get_format_config(
                inc_gen, inc_char, inc_copy, inc_art, inc_meta,
                rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix,
                strip_tags, strip_tags_enable
            )

            results: list[GachaPullResult] = await pull_gacha(
                site=site_key,
                count=count,
                include=inc_tags,
                exclude=exc_tags,
                rating=rating_val,
                min_score=int(min_score_val),
                config=fmt_config,
            )

            if not results:
                status = """
                <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; padding: 8px 12px; border-radius: 6px; color: #ef4444;">
                    No posts found matching criteria or site is unavailable. Try adjusting Include/Exclude tags or score.
                </div>
                """
                return (
                    "", status, [], None, "", "", "", "", "",
                    [], 0, history, history_idx
                )

            # Build Gallery items
            gallery_items = []
            for r in results:
                if r.image:
                    gallery_items.append((r.image, r.get_gallery_caption()))
                elif r.post.preview_url:
                    gallery_items.append((r.post.preview_url, r.get_gallery_caption()))

            # Multi-pull stats summary
            stats_banner = get_multi_pull_stats_html(results)

            # Primary selected card is the first one
            first = results[0]
            first_status = first.to_summary_html()
            first_chips = first.to_tag_chips_html()

            artist_str = ", ".join(TagFormatter.format_artist_tags(first.post.tags_artist, fmt_config)) if first.post.tags_artist else ""
            char_str = ", ".join(TagFormatter.format_character_tags(first.post.tags_character, fmt_config)) if first.post.tags_character else ""
            copy_str = ", ".join(TagFormatter.format_copyright_tags(first.post.tags_copyright, fmt_config)) if first.post.tags_copyright else ""

            # Append to session navigation history
            new_history = list(history[:history_idx + 1] if history_idx >= 0 else [])
            new_history.append(first)
            new_idx = len(new_history) - 1

            return (
                stats_banner,
                first_status,
                gallery_items,
                first.image or first.post.preview_url,
                first_chips,
                first.full_prompt,
                artist_str,
                char_str,
                copy_str,
                results,
                0,
                new_history,
                new_idx,
            )

        # Wire Pull Buttons
        async def _pull_1x(*args):
            return await _do_gacha_pull(1, *args)

        async def _pull_5x(*args):
            return await _do_gacha_pull(5, *args)

        async def _pull_10x(*args):
            return await _do_gacha_pull(10, *args)

        pull_inputs = [
            preset_dropdown,
            site_dropdown, rating_dropdown, min_score_number, include_tags_box, exclude_tags_box,
            inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
            replace_underscores_chk, escape_parens_chk, artist_fmt_dropdown, artist_weight_slider,
            max_tags_slider, tag_prefix_box, tag_suffix_box,
            strip_tags_box, strip_tags_chk,
            history_state, history_idx_state,
        ]
        pull_outputs = [
            stats_banner_html, status_html, gacha_gallery, preview_image, tag_chips_html,
            full_tags_textbox, artist_tags_box, character_tags_box, copyright_tags_box,
            gacha_results_state, active_card_idx_state, history_state, history_idx_state,
        ]

        pull_1x_evt = pull_1x_btn.click(fn=_pull_1x, inputs=pull_inputs, outputs=pull_outputs, show_progress="minimal")
        pull_5x_evt = pull_5x_btn.click(fn=_pull_5x, inputs=pull_inputs, outputs=pull_outputs, show_progress="minimal")
        pull_10x_evt = pull_10x_btn.click(fn=_pull_10x, inputs=pull_inputs, outputs=pull_outputs, show_progress="minimal")

        cancel_pull_btn.click(fn=None, inputs=None, outputs=None, cancels=[pull_1x_evt, pull_5x_evt, pull_10x_evt], show_progress="hidden")

        # Event: Gallery Card Click Selection
        def _on_gallery_select(evt: gr.SelectData, results_list, history, history_idx):
            if not results_list or evt.index >= len(results_list):
                return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), evt.index, history, history_idx
            
            selected: GachaPullResult = results_list[evt.index]
            status = selected.to_summary_html()
            chips = selected.to_tag_chips_html()
            artist_str = ", ".join(TagFormatter.format_artist_tags(selected.post.tags_artist, selected.config)) if selected.post.tags_artist else ""
            char_str = ", ".join(TagFormatter.format_character_tags(selected.post.tags_character, selected.config)) if selected.post.tags_character else ""
            copy_str = ", ".join(TagFormatter.format_copyright_tags(selected.post.tags_copyright, selected.config)) if selected.post.tags_copyright else ""

            new_history = list(history[:history_idx + 1] if history_idx >= 0 else [])
            new_history.append(selected)
            new_idx = len(new_history) - 1

            return (
                status,
                selected.image or selected.post.preview_url,
                chips,
                selected.full_prompt,
                artist_str,
                char_str,
                copy_str,
                evt.index,
                new_history,
                new_idx,
            )

        gacha_gallery.select(
            fn=_on_gallery_select,
            inputs=[gacha_results_state, history_state, history_idx_state],
            outputs=[
                status_html, preview_image, tag_chips_html, full_tags_textbox,
                artist_tags_box, character_tags_box, copyright_tags_box,
                active_card_idx_state, history_state, history_idx_state,
            ],
            show_progress="hidden",
        )

        # History Navigation
        def _on_prev_history(history, idx):
            if history and idx > 0:
                prev_card: GachaPullResult = history[idx - 1]
                artist_str = ", ".join(TagFormatter.format_artist_tags(prev_card.post.tags_artist, prev_card.config)) if prev_card.post.tags_artist else ""
                char_str = ", ".join(TagFormatter.format_character_tags(prev_card.post.tags_character, prev_card.config)) if prev_card.post.tags_character else ""
                copy_str = ", ".join(TagFormatter.format_copyright_tags(prev_card.post.tags_copyright, prev_card.config)) if prev_card.post.tags_copyright else ""
                return (
                    prev_card.to_summary_html(),
                    prev_card.image or prev_card.post.preview_url,
                    prev_card.to_tag_chips_html(),
                    prev_card.full_prompt,
                    artist_str,
                    char_str,
                    copy_str,
                    idx - 1,
                )
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), idx

        def _on_next_history(history, idx):
            if history and idx < len(history) - 1:
                next_card: GachaPullResult = history[idx + 1]
                artist_str = ", ".join(TagFormatter.format_artist_tags(next_card.post.tags_artist, next_card.config)) if next_card.post.tags_artist else ""
                char_str = ", ".join(TagFormatter.format_character_tags(next_card.post.tags_character, next_card.config)) if next_card.post.tags_character else ""
                copy_str = ", ".join(TagFormatter.format_copyright_tags(next_card.post.tags_copyright, next_card.config)) if next_card.post.tags_copyright else ""
                return (
                    next_card.to_summary_html(),
                    next_card.image or next_card.post.preview_url,
                    next_card.to_tag_chips_html(),
                    next_card.full_prompt,
                    artist_str,
                    char_str,
                    copy_str,
                    idx + 1,
                )
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), idx

        prev_btn.click(
            fn=_on_prev_history,
            inputs=[history_state, history_idx_state],
            outputs=[
                status_html, preview_image, tag_chips_html, full_tags_textbox,
                artist_tags_box, character_tags_box, copyright_tags_box,
                history_idx_state,
            ],
            show_progress="hidden",
        )

        next_btn.click(
            fn=_on_next_history,
            inputs=[history_state, history_idx_state],
            outputs=[
                status_html, preview_image, tag_chips_html, full_tags_textbox,
                artist_tags_box, character_tags_box, copyright_tags_box,
                history_idx_state,
            ],
            show_progress="hidden",
        )

        def _on_clear():
            return "", "", [], None, "", "", "", "", "", [], 0, [], -1

        clear_btn.click(
            fn=_on_clear,
            inputs=None,
            outputs=[
                stats_banner_html, status_html, gacha_gallery, preview_image, tag_chips_html,
                full_tags_textbox, artist_tags_box, character_tags_box, copyright_tags_box,
                gacha_results_state, active_card_idx_state, history_state, history_idx_state,
            ],
            show_progress="hidden",
        )

        # Event: Save to Favorites
        def _on_save_favorite(results_list, idx, full_prompt):
            if results_list and idx < len(results_list):
                card: GachaPullResult = results_list[idx]
                added = favorites.add_favorite(card.post, card.site, full_prompt)
                if added:
                    gr.Info("Card added to Favorites")
                else:
                    gr.Warning("This post is already in Favorites")
                
                # Refresh favorites list
                fav_choices = _safe_get_fav_choices()
                return gr.Dropdown(choices=fav_choices, value=fav_choices[0] if fav_choices else None)
            return gr.update()

        fav_post_btn.click(
            fn=_on_save_favorite,
            inputs=[gacha_results_state, active_card_idx_state, full_tags_textbox],
            outputs=[fav_dropdown],
            show_progress="hidden",
        )

        # Event: Load Favorite
        def _on_load_favorite(fav_str):
            if not fav_str:
                return gr.update(), gr.update(), gr.update(), gr.update()
            
            all_favs = favorites.load_favorites()
            for f in all_favs:
                repr_str = f"[{f.get('rarity', 'R')}] #{f.get('id')} ({f.get('site')}) - {', '.join(f.get('tags_artist', []) or ['unknown'])}"
                if repr_str == fav_str or f"#{f.get('id')}" in fav_str:
                    full_p = f.get("formatted_prompt", "") or ", ".join(f.get("all_tags", []))
                    art_p = ", ".join(f.get("tags_artist", []))
                    char_p = ", ".join(f.get("tags_character", []))
                    copy_p = ", ".join(f.get("tags_copyright", []))
                    gr.Info(f"Loaded favorite post #{f.get('id')}")
                    return full_p, art_p, char_p, copy_p
            return gr.update(), gr.update(), gr.update(), gr.update()

        fav_load_btn.click(
            fn=_on_load_favorite,
            inputs=[fav_dropdown],
            outputs=[full_tags_textbox, artist_tags_box, character_tags_box, copyright_tags_box],
            show_progress="hidden",
        )

        # Event: Delete Favorite
        def _on_delete_favorite(fav_str):
            if not fav_str:
                return gr.update()
            
            all_favs = favorites.load_favorites()
            for f in all_favs:
                repr_str = f"[{f.get('rarity', 'R')}] #{f.get('id')} ({f.get('site')}) - {', '.join(f.get('tags_artist', []) or ['unknown'])}"
                if repr_str == fav_str or f"#{f.get('id')}" in fav_str:
                    favorites.remove_favorite(f.get("fav_id"))
                    break

            fav_choices = _safe_get_fav_choices()
            gr.Info("Favorite deleted")
            return gr.Dropdown(choices=fav_choices, value=fav_choices[0] if fav_choices else None)

        fav_del_btn.click(
            fn=_on_delete_favorite,
            inputs=[fav_dropdown],
            outputs=[fav_dropdown],
            show_progress="hidden",
        )

        # Event: Clear All Favorites
        def _on_clear_all_favs():
            favorites.clear_favorites()
            gr.Info("All favorites cleared")
            return gr.Dropdown(choices=[], value=None)

        fav_clear_all_btn.click(
            fn=_on_clear_all_favs,
            inputs=None,
            outputs=[fav_dropdown],
            show_progress="hidden",
        )

        # Prompt Targets Binding
        target_prompt = self.img2img_prompt if is_img2img else self.txt2img_prompt
        target_neg_prompt = self.img2img_neg_prompt if is_img2img else self.txt2img_neg_prompt

        with contextlib.suppress(AttributeError):
            def _transfer_append(res, cur, strip_tags, strip_tags_enable):
                text = f"{cur}, {res}".strip(", ") if cur else res
                if strip_tags_enable and strip_tags:
                    cfg = TagFormatConfig(strip_tags=strip_tags, strip_tags_enable=strip_tags_enable)
                    text = TagFormatter.strip_prompt_text(text, cfg)
                return text

            def _transfer_replace(res, strip_tags, strip_tags_enable):
                if strip_tags_enable and strip_tags:
                    cfg = TagFormatConfig(strip_tags=strip_tags, strip_tags_enable=strip_tags_enable)
                    return TagFormatter.strip_prompt_text(res, cfg)
                return res

            def _transfer_prepend(res, cur, strip_tags, strip_tags_enable):
                text = f"{res}, {cur}".strip(", ") if cur else res
                if strip_tags_enable and strip_tags:
                    cfg = TagFormatConfig(strip_tags=strip_tags, strip_tags_enable=strip_tags_enable)
                    text = TagFormatter.strip_prompt_text(text, cfg)
                return text

            def _transfer_insert_gacha(cur):
                token = "[gacha]"
                if not cur or not cur.strip():
                    new_prompt = token
                elif token in cur:
                    new_prompt = cur
                else:
                    new_prompt = f"{cur.strip().rstrip(',')}, {token}"

                try:
                    shared.opts.set("gpr_auto_gacha_enable", True)
                    shared.opts.save(shared.config_filename)
                except Exception:
                    pass

                gr.Info("Inserted [gacha] into prompt and enabled Auto-Gacha! Each image in your batch will receive a unique random card.")
                return new_prompt, True

            if target_prompt is not None:
                insert_gacha_btn.click(
                    fn=_transfer_insert_gacha,
                    inputs=[target_prompt],
                    outputs=[target_prompt, auto_gacha_chk],
                )
                append_prompt_btn.click(
                    fn=_transfer_append,
                    inputs=[full_tags_textbox, target_prompt, strip_tags_box, strip_tags_chk],
                    outputs=[target_prompt],
                )
                replace_prompt_btn.click(
                    fn=_transfer_replace,
                    inputs=[full_tags_textbox, strip_tags_box, strip_tags_chk],
                    outputs=[target_prompt],
                )
                prepend_prompt_btn.click(
                    fn=_transfer_prepend,
                    inputs=[full_tags_textbox, target_prompt, strip_tags_box, strip_tags_chk],
                    outputs=[target_prompt],
                )
                insert_artist_btn.click(
                    fn=_transfer_append,
                    inputs=[artist_tags_box, target_prompt, strip_tags_box, strip_tags_chk],
                    outputs=[target_prompt],
                )
                insert_character_btn.click(
                    fn=_transfer_append,
                    inputs=[character_tags_box, target_prompt, strip_tags_box, strip_tags_chk],
                    outputs=[target_prompt],
                )

            if target_neg_prompt is not None:
                add_negative_btn.click(
                    fn=lambda exc, cur: f"{cur}, {exc}".strip(", ") if cur else exc,
                    inputs=[exclude_tags_box, target_neg_prompt],
                    outputs=[target_neg_prompt],
                )

            def _save_auto_gacha_settings(enabled, mode):
                try:
                    shared.opts.set("gpr_auto_gacha_enable", bool(enabled))
                    shared.opts.set("gpr_auto_gacha_mode", str(mode))
                    shared.opts.save(shared.config_filename)
                except Exception:
                    pass

            auto_gacha_chk.change(
                fn=_save_auto_gacha_settings,
                inputs=[auto_gacha_chk, auto_mode_dropdown],
                outputs=None,
                show_progress="hidden",
            )
            auto_mode_dropdown.change(
                fn=_save_auto_gacha_settings,
                inputs=[auto_gacha_chk, auto_mode_dropdown],
                outputs=None,
                show_progress="hidden",
            )

        return [
            auto_gacha_chk, auto_mode_dropdown, auto_neg_chk,
            site_dropdown, rating_dropdown, min_score_number,
            include_tags_box, exclude_tags_box,
            inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
            replace_underscores_chk, escape_parens_chk, artist_fmt_dropdown, artist_weight_slider,
            max_tags_slider, tag_prefix_box, tag_suffix_box,
            strip_tags_box, strip_tags_chk,
        ]

    def after_component(self, component, **kwargs):
        elem_id = kwargs.get("elem_id")
        if elem_id == "txt2img_prompt":
            self.txt2img_prompt = component
        elif elem_id == "txt2img_neg_prompt":
            self.txt2img_neg_prompt = component
        elif elem_id == "img2img_prompt":
            self.img2img_prompt = component
        elif elem_id == "img2img_neg_prompt":
            self.img2img_neg_prompt = component

    def process(
        self,
        p,
        auto_gacha_chk,
        auto_mode_dropdown,
        auto_neg_chk,
        site_lbl,
        rating_val,
        min_score_val,
        inc_tags,
        exc_tags,
        inc_gen,
        inc_char,
        inc_copy,
        inc_art,
        inc_meta,
        rep_under,
        esc_par,
        art_fmt,
        art_wt,
        max_tags,
        prefix,
        suffix,
        strip_tags_box=None,
        strip_tags_chk=None,
        *args
    ):
        """Auto-Gacha process hook: replaces placeholders or auto-injects tags into prompt per generation."""
        tokens = ("[gacha]", "[gacha-wa]", "[gacha-oa]", "[gacha-oc]", "[gacha-gen]", "[gacha-all]")
        prompt_str = str(p.prompt or "").lower()
        all_prompts_str = " ".join(str(x) for x in (getattr(p, "all_prompts", []) or [])).lower()
        prompt_has_placeholder = any(t in prompt_str or t in all_prompts_str for t in tokens)

        if not auto_gacha_chk and not prompt_has_placeholder:
            return

        # Safe argument extraction with sensible defaults from active settings
        auto_gacha_chk = bool(auto_gacha_chk) if auto_gacha_chk is not None else False
        auto_mode_dropdown = str(auto_mode_dropdown or "Replace Full Prompt")
        auto_neg_chk = bool(auto_neg_chk) if auto_neg_chk is not None else False

        site_str = str(site_lbl or "").strip()
        site_key = SITE_KEY_BY_LABEL.get(site_str, site_str.lower() if site_str else DEFAULT_SITE) or DEFAULT_SITE
        if site_key not in SITE_LABEL_BY_KEY:
            site_key = DEFAULT_SITE

        rating_val = str(rating_val or "safe").strip().lower()
        try:
            min_score_val = int(min_score_val or 0)
        except (ValueError, TypeError):
            min_score_val = 0

        inc_tags = str(inc_tags or "").strip()
        exc_tags = str(exc_tags or "").strip()

        inc_gen = bool(inc_gen) if inc_gen is not None else True
        inc_char = bool(inc_char) if inc_char is not None else True
        inc_copy = bool(inc_copy) if inc_copy is not None else True
        inc_art = bool(inc_art) if inc_art is not None else True
        inc_meta = bool(inc_meta) if inc_meta is not None else False

        rep_under = bool(rep_under) if rep_under is not None else True
        esc_par = bool(esc_par) if esc_par is not None else True

        art_fmt = str(art_fmt or "raw")
        try:
            art_wt = float(art_wt if art_wt is not None else 1.1)
        except (ValueError, TypeError):
            art_wt = 1.1

        try:
            max_tags = int(max_tags if max_tags is not None else 25)
        except (ValueError, TypeError):
            max_tags = 25

        prefix = str(prefix or "").strip()
        suffix = str(suffix or "").strip()

        strip_tags_str = str(strip_tags_box if strip_tags_box is not None else getattr(shared.opts, "gpr_strip_tags", "loli, shota, ai generated"))
        strip_tags_enabled = bool(strip_tags_chk if strip_tags_chk is not None else getattr(shared.opts, "gpr_strip_tags_enable", True))

        blacklist_raw = getattr(shared.opts, "gpr_universalBlacklist", "") or ""
        bl_list = [t.strip() for t in blacklist_raw.split(',') if t.strip()]

        fmt_config = TagFormatConfig(
            include_general=inc_gen,
            include_character=inc_char,
            include_copyright=inc_copy,
            include_artist=inc_art,
            include_meta=inc_meta,
            replace_underscores=rep_under,
            escape_parentheses=esc_par,
            artist_format=art_fmt,
            artist_weight=art_wt,
            max_general_tags=max_tags,
            prefix=prefix,
            suffix=suffix,
            blacklist=bl_list,
            strip_tags=strip_tags_str,
            strip_tags_enable=strip_tags_enabled,
        )

        batch_size = max(getattr(p, "batch_size", 1) or 1, 1)
        n_iter = max(getattr(p, "n_iter", 1) or 1, 1)
        total_images = batch_size * n_iter

        # Roll posts for the batch without downloading image thumbnails (ultra fast)
        results = _run_async(
            pull_gacha(
                site=site_key,
                count=total_images,
                include=inc_tags,
                exclude=exc_tags,
                rating=rating_val,
                min_score=min_score_val,
                config=fmt_config,
                fetch_images=False,
            )
        )

        if not results:
            print(f"[Booru Tags Gacha] No posts matched criteria for Auto-Gacha ({site_key})")
            import random
            base_seed = getattr(p, "seed", -1)
            try:
                base_seed_int = int(base_seed)
            except (ValueError, TypeError):
                base_seed_int = -1
            if base_seed_int in (-1, None):
                p.all_seeds = [random.randint(1, 2147483647) for _ in range(total_images)]
            else:
                p.all_seeds = [base_seed_int + i for i in range(total_images)]
            p.seeds = p.all_seeds[:batch_size]
            return

        all_prompts = list(getattr(p, "all_prompts", []))
        all_neg_prompts = list(getattr(p, "all_negative_prompts", []))

        base_prompt = all_prompts[0] if all_prompts else (p.prompt or "")
        base_neg = all_neg_prompts[0] if all_neg_prompts else (p.negative_prompt or "")

        if len(all_prompts) < total_images:
            all_prompts = [base_prompt] * total_images
        if len(all_neg_prompts) < total_images:
            all_neg_prompts = [base_neg] * total_images

        print(f"[Booru Tags Gacha] Auto-Gacha active for {total_images} image(s) [Site: {site_key}, Unique Cards: {len(results)}]")

        for idx in range(total_images):
            card = results[idx % len(results)]
            cur_prompt = all_prompts[idx]

            # 1. Replace placeholders if present
            updated_prompt, was_replaced = TagFormatter.replace_placeholders(
                cur_prompt, card.post, fmt_config
            )

            # 2. If no placeholders and Auto-Gacha is enabled
            if not was_replaced and auto_gacha_chk:
                tag_string = card.full_prompt
                if auto_mode_dropdown == "Replace Full Prompt":
                    updated_prompt = tag_string
                elif auto_mode_dropdown == "Replace [gacha...] placeholders":
                    # If cur_prompt matches the un-expanded base prompt or is empty, replace fully per batch item
                    if not cur_prompt.strip() or cur_prompt == base_prompt:
                        updated_prompt = tag_string
                    else:
                        updated_prompt = f"{cur_prompt}, {tag_string}".strip(", ")
                elif auto_mode_dropdown == "Append to Prompt":
                    updated_prompt = f"{cur_prompt}, {tag_string}".strip(", ")
                elif auto_mode_dropdown == "Prepend to Prompt":
                    updated_prompt = f"{tag_string}, {cur_prompt}".strip(", ")

            if fmt_config.strip_tags_enable and fmt_config.blacklist:
                updated_prompt = TagFormatter.strip_prompt_text(updated_prompt, fmt_config)

            all_prompts[idx] = updated_prompt

            if auto_neg_chk and exc_tags:
                cur_neg = all_neg_prompts[idx]
                all_neg_prompts[idx] = f"{cur_neg}, {exc_tags}".strip(", ")

            caption = card.get_gallery_caption()
            print(f"  [Auto-Gacha #{idx + 1}/{total_images}] Post #{card.post.id} ({card.tier}): {caption}")

        p.prompt = all_prompts[0]
        p.all_prompts = all_prompts

        p.negative_prompt = all_neg_prompts[0]
        p.all_negative_prompts = all_neg_prompts

        # Update initial batch slice
        p.prompts = all_prompts[:batch_size]
        p.negative_prompts = all_neg_prompts[:batch_size]

        # Update main prompt references
        p.main_prompt = all_prompts[0]
        if hasattr(p, "main_negative_prompt"):
            p.main_negative_prompt = all_neg_prompts[0]

        # Support Hires Fix prompts
        if hasattr(p, "all_hr_prompts"):
            p.all_hr_prompts = list(all_prompts)
        if hasattr(p, "hr_prompt"):
            p.hr_prompt = all_prompts[0]
        if hasattr(p, "all_hr_negative_prompts"):
            p.all_hr_negative_prompts = list(all_neg_prompts)
        if hasattr(p, "hr_negative_prompt"):
            p.hr_negative_prompt = all_neg_prompts[0]

        if hasattr(p, "_all_prompts_c"):
            p._all_prompts_c = list(all_prompts)
        if hasattr(p, "_all_negative_prompts_c"):
            p._all_negative_prompts_c = list(all_neg_prompts)

        # Strictly diversify seeds across every single image in the batch
        import random
        base_seed = getattr(p, "seed", -1)
        try:
            base_seed_int = int(base_seed)
        except (ValueError, TypeError):
            base_seed_int = -1

        if base_seed_int in (-1, None):
            p.all_seeds = [random.randint(1, 2147483647) for _ in range(total_images)]
            p.seed = p.all_seeds[0]
        else:
            p.all_seeds = [base_seed_int + i for i in range(total_images)]

        base_subseed = getattr(p, "subseed", -1)
        try:
            base_sub_int = int(base_subseed)
        except (ValueError, TypeError):
            base_sub_int = -1

        if base_sub_int in (-1, None):
            p.all_subseeds = [random.randint(1, 2147483647) for _ in range(total_images)]
            p.subseed = p.all_subseeds[0]
        else:
            p.all_subseeds = [base_sub_int + i for i in range(total_images)]

        p.seeds = p.all_seeds[:batch_size]
        p.subseeds = p.all_subseeds[:batch_size]

    def process_batch(self, p, *args, **kwargs):
        """Ensure batch-level prompts and seeds match the current iteration."""
        batch_num = kwargs.get("batch_number", getattr(p, "iteration", 0))
        batch_size = max(getattr(p, "batch_size", 1) or 1, 1)
        start_idx = batch_num * batch_size
        end_idx = start_idx + batch_size

        if hasattr(p, "all_prompts") and len(p.all_prompts) > start_idx:
            p.prompts = p.all_prompts[start_idx:min(end_idx, len(p.all_prompts))]
        if hasattr(p, "all_negative_prompts") and len(p.all_negative_prompts) > start_idx:
            p.negative_prompts = p.all_negative_prompts[start_idx:min(end_idx, len(p.all_negative_prompts))]
        if hasattr(p, "all_seeds") and len(p.all_seeds) > start_idx:
            p.seeds = p.all_seeds[start_idx:min(end_idx, len(p.all_seeds))]
        if hasattr(p, "all_subseeds") and len(p.all_subseeds) > start_idx:
            p.subseeds = p.all_subseeds[start_idx:min(end_idx, len(p.all_subseeds))]
        if getattr(p, "enable_hr", False):
            if hasattr(p, "all_hr_prompts") and len(p.all_hr_prompts) > start_idx:
                p.hr_prompts = p.all_hr_prompts[start_idx:min(end_idx, len(p.all_hr_prompts))]
            if hasattr(p, "all_hr_negative_prompts") and len(p.all_hr_negative_prompts) > start_idx:
                p.hr_negative_prompts = p.all_hr_negative_prompts[start_idx:min(end_idx, len(p.all_hr_negative_prompts))]


def on_ui_settings():
    GPR_SECTION = ("gpr", EXTENSION_NAME)

    gpr_options = {
        "gpr_danbooru_username": shared.OptionInfo("", "Danbooru Username", gr.Textbox).info(
            "Account login name. Required together with API key for unlimited tags."
        ),
        "gpr_danbooru_api_key": shared.OptionInfo("", "Danbooru API Key", gr.Textbox).info(
            '<a href="https://danbooru.donmai.us/profile" target="_blank">Profile → API Key</a>.'
        ),
        "gpr_aibooru_username": shared.OptionInfo("", "AIBooru Username", gr.Textbox),
        "gpr_aibooru_api_key": shared.OptionInfo("", "AIBooru API Key", gr.Textbox).info(
            '<a href="https://aibooru.online/profile" target="_blank">AIBooru Profile</a>.'
        ),
        "gpr_api_key": shared.OptionInfo("", "Gelbooru API Key", gr.Textbox).info(
            '<a href="https://gelbooru.com/index.php?page=account&s=options" target="_blank">Account Options</a>.'
        ),
        "gpr_user_id": shared.OptionInfo("", "Gelbooru User ID", gr.Textbox).info(
            '<a href="https://gelbooru.com/index.php?page=account&s=options" target="_blank">Account Options</a>.'
        ),
        "gpr_rule34_api_key": shared.OptionInfo("", "Rule34 API Key", gr.Textbox).info(
            '<a href="https://rule34.xxx/index.php?page=account&s=options" target="_blank">Rule34 Account Options</a>.'
        ),
        "gpr_rule34_user_id": shared.OptionInfo("", "Rule34 User ID", gr.Textbox).info(
            '<a href="https://rule34.xxx/index.php?page=account&s=options" target="_blank">Rule34 Account Options</a>.'
        ),
        "gpr_e621_username": shared.OptionInfo("", "e621 / e926 Username", gr.Textbox).info("Optional username."),
        "gpr_e621_api_key": shared.OptionInfo("", "e621 / e926 API Key", gr.Textbox).info(
            '<a href="https://e621.net/users/home" target="_blank">Account → Manage API Access</a>.'
        ),
        "gpr_derpibooru_api_key": shared.OptionInfo("", "Derpibooru API Key", gr.Textbox).info(
            '<a href="https://derpibooru.org/users/edit" target="_blank">Derpibooru Account</a>.'
        ),
        "gpr_custom_engine": shared.OptionInfo(
            "gelbooru",
            "Custom Booru Engine Type",
            gr.Dropdown,
            lambda: {"choices": ["danbooru", "moebooru", "gelbooru", "e621", "philomena"]},
        ),
        "gpr_custom_base_url": shared.OptionInfo("https://tbib.org/", "Custom Booru Base URL", gr.Textbox),
        "gpr_custom_api_key": shared.OptionInfo("", "Custom Booru API Key", gr.Textbox),
        "gpr_custom_user_id": shared.OptionInfo("", "Custom Booru User ID / Username", gr.Textbox),
        "gpr_universalBlacklist": shared.OptionInfo(
            "loli, shota, ai_generated",
            "Universal Tag Blacklist",
            gr.Textbox,
        ).info("Comma-separated tags to always exclude from booru search rolls."),
        "gpr_strip_tags": shared.OptionInfo(
            "loli, shota, ai generated",
            "Tags to Strip from Prompt",
            gr.Textbox,
        ).info("Comma-separated tags to strip from prompts during generation or prompt transfer."),
        "gpr_strip_tags_enable": shared.OptionInfo(
            True,
            "Enable Tag Stripping from Prompt",
            gr.Checkbox,
        ),
        "gpr_auto_gacha_enable": shared.OptionInfo(
            False,
            "Enable Auto-Gacha on Generate by Default",
            gr.Checkbox,
        ).info("When checked, every generation automatically rolls distinct tags for every image in your batch."),
        "gpr_auto_gacha_mode": shared.OptionInfo(
            "Replace Full Prompt",
            "Default Auto-Gacha Mode",
            gr.Dropdown,
            lambda: {"choices": [
                "Replace Full Prompt",
                "Replace [gacha...] placeholders",
                "Append to Prompt",
                "Prepend to Prompt",
            ]},
        ),
    }

    for key, opt in gpr_options.items():
        opt.section = GPR_SECTION
        shared.opts.add_option(key, opt)


script_callbacks.on_ui_settings(on_ui_settings)
