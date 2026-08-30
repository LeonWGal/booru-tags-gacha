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
        default_preset_name = all_preset_names[0] if all_preset_names else "Anime Solo Girl"
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
                        height=360,
                        show_label=False,
                        show_download_button=True,
                        show_share_button=True,
                        elem_classes=["gacha-preview-image"],
                    )
                with gr.Column(scale=2, min_width=300, elem_classes=["gacha-gallery-col"]):
                    gacha_gallery = gr.Gallery(
                        label="Gacha Multi-Pull Cards",
                        show_label=False,
                        elem_id="booru_gacha_gallery",
                        elem_classes=["gacha-gallery-grid"],
                        columns=[2, 3, 5],
                        rows=[1, 2],
                        height=360,
                        object_fit="cover",
                        preview=False,
                        allow_preview=False,
                        show_download_button=True,
                        show_share_button=True,
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
                append_prompt_btn = gr.Button("Append Prompt", elem_classes=["gacha-action-btn", "gacha-insert-btn"])
                replace_prompt_btn = gr.Button("Replace Prompt", elem_classes=["gacha-action-btn", "gacha-insert-btn"])
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

            # Collapsible Auto-Gacha on Generate
            with gr.Accordion("Auto-Gacha on Generate", open=False):
                gr.Markdown(
                    "Automatically roll random tags on every generation. "
                    "Supports placeholder substitution: `[gacha]` (full prompt), `[gacha-wa]` (without artist), "
                    "`[gacha-oa]` (only artist), `[gacha-oc]` (only character), `[gacha-gen]` (only general)."
                )
                with gr.Row():
                    auto_gacha_chk = gr.Checkbox(label="Enable Auto-Gacha on Generate", value=False)
                    auto_mode_dropdown = gr.Dropdown(
                        label="Auto-Gacha Mode",
                        choices=[
                            "Replace [gacha...] placeholders",
                            "Append to Prompt",
                            "Prepend to Prompt",
                            "Replace Full Prompt",
                        ],
                        value="Replace [gacha...] placeholders",
                    )
                    auto_neg_chk = gr.Checkbox(label="Auto-Add Exclude Tags to Negative", value=False)

        # Helper to construct TagFormatConfig from UI values
        def _get_format_config(
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix
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
            )

        preset_dropdown.change(
            fn=_on_preset_change,
            inputs=[preset_dropdown],
            outputs=[
                site_dropdown, rating_dropdown, min_score_number,
                include_tags_box, exclude_tags_box,
                inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
                artist_fmt_dropdown, artist_weight_slider, max_tags_slider,
            ],
        )

        # Event: Save Preset
        def _on_save_preset(
            preset_name, site_lbl, rating_val, score_val, inc_val, exc_val,
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            art_fmt, art_wt, max_tags
        ):
            site_k = SITE_KEY_BY_LABEL.get(site_lbl, DEFAULT_SITE)
            data = {
                "site": site_k,
                "rating": rating_val,
                "min_score": int(score_val),
                "include": inc_val,
                "exclude": exc_val,
                "include_general": inc_gen,
                "include_character": inc_char,
                "include_copyright": inc_copy,
                "include_artist": inc_art,
                "include_meta": inc_meta,
                "artist_format": art_fmt,
                "artist_weight": float(art_wt),
                "max_general_tags": int(max_tags),
            }
            presets.save_preset(preset_name, data)
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
            count, site_lbl, rating_val, min_score_val, inc_tags, exc_tags,
            inc_gen, inc_char, inc_copy, inc_art, inc_meta,
            rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix,
            history, history_idx,
        ):
            site_key = SITE_KEY_BY_LABEL.get(site_lbl, DEFAULT_SITE)
            fmt_config = _get_format_config(
                inc_gen, inc_char, inc_copy, inc_art, inc_meta,
                rep_under, esc_par, art_fmt, art_wt, max_tags, prefix, suffix
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
            site_dropdown, rating_dropdown, min_score_number, include_tags_box, exclude_tags_box,
            inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
            replace_underscores_chk, escape_parens_chk, artist_fmt_dropdown, artist_weight_slider,
            max_tags_slider, tag_prefix_box, tag_suffix_box,
            history_state, history_idx_state,
        ]
        pull_outputs = [
            stats_banner_html, status_html, gacha_gallery, preview_image, tag_chips_html,
            full_tags_textbox, artist_tags_box, character_tags_box, copyright_tags_box,
            gacha_results_state, active_card_idx_state, history_state, history_idx_state,
        ]

        pull_1x_evt = pull_1x_btn.click(fn=_pull_1x, inputs=pull_inputs, outputs=pull_outputs)
        pull_5x_evt = pull_5x_btn.click(fn=_pull_5x, inputs=pull_inputs, outputs=pull_outputs)
        pull_10x_evt = pull_10x_btn.click(fn=_pull_10x, inputs=pull_inputs, outputs=pull_outputs)

        cancel_pull_btn.click(fn=None, inputs=None, outputs=None, cancels=[pull_1x_evt, pull_5x_evt, pull_10x_evt])

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
        )

        next_btn.click(
            fn=_on_next_history,
            inputs=[history_state, history_idx_state],
            outputs=[
                status_html, preview_image, tag_chips_html, full_tags_textbox,
                artist_tags_box, character_tags_box, copyright_tags_box,
                history_idx_state,
            ],
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
        )

        # Prompt Targets Binding
        target_prompt = self.img2img_prompt if is_img2img else self.txt2img_prompt
        target_neg_prompt = self.img2img_neg_prompt if is_img2img else self.txt2img_neg_prompt

        with contextlib.suppress(AttributeError):
            if target_prompt is not None:
                append_prompt_btn.click(
                    fn=lambda res, cur: f"{cur}, {res}".strip(", ") if cur else res,
                    inputs=[full_tags_textbox, target_prompt],
                    outputs=[target_prompt],
                )
                replace_prompt_btn.click(
                    fn=lambda res: res,
                    inputs=[full_tags_textbox],
                    outputs=[target_prompt],
                )
                prepend_prompt_btn.click(
                    fn=lambda res, cur: f"{res}, {cur}".strip(", ") if cur else res,
                    inputs=[full_tags_textbox, target_prompt],
                    outputs=[target_prompt],
                )
                insert_artist_btn.click(
                    fn=lambda res, cur: f"{cur}, {res}".strip(", ") if cur else res,
                    inputs=[artist_tags_box, target_prompt],
                    outputs=[target_prompt],
                )
                insert_character_btn.click(
                    fn=lambda res, cur: f"{cur}, {res}".strip(", ") if cur else res,
                    inputs=[character_tags_box, target_prompt],
                    outputs=[target_prompt],
                )

            if target_neg_prompt is not None:
                add_negative_btn.click(
                    fn=lambda exc, cur: f"{cur}, {exc}".strip(", ") if cur else exc,
                    inputs=[exclude_tags_box, target_neg_prompt],
                    outputs=[target_neg_prompt],
                )

        return [
            auto_gacha_chk, auto_mode_dropdown, auto_neg_chk,
            site_dropdown, rating_dropdown, min_score_number,
            include_tags_box, exclude_tags_box,
            inc_general_chk, inc_char_chk, inc_copy_chk, inc_artist_chk, inc_meta_chk,
            replace_underscores_chk, escape_parens_chk, artist_fmt_dropdown, artist_weight_slider,
            max_tags_slider, tag_prefix_box, tag_suffix_box,
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
        *args
    ):
        """Auto-Gacha process hook: replaces placeholders or auto-injects tags into prompt per generation."""
        prompt_has_placeholder = any(
            token in (p.prompt or "")
            for token in ("[gacha]", "[gacha-wa]", "[gacha-oa]", "[gacha-oc]", "[gacha-gen]", "[gacha-all]")
        )

        if not auto_gacha_chk and not prompt_has_placeholder:
            return

        site_key = SITE_KEY_BY_LABEL.get(site_lbl, DEFAULT_SITE)
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
            max_general_tags=int(max_tags),
            prefix=prefix,
            suffix=suffix,
            blacklist=bl_list,
        )

        batch_size = getattr(p, "batch_size", 1)
        n_iter = getattr(p, "n_iter", 1)
        total_images = batch_size * n_iter

        # Roll posts for the batch
        results = _run_async(
            pull_gacha(
                site=site_key,
                count=total_images,
                include=inc_tags,
                exclude=exc_tags,
                rating=rating_val,
                min_score=int(min_score_val),
                config=fmt_config,
            )
        )

        if not results:
            return

        all_prompts = list(getattr(p, "all_prompts", [p.prompt]))
        all_neg_prompts = list(getattr(p, "all_negative_prompts", [p.negative_prompt]))

        for idx in range(len(all_prompts)):
            card = results[idx % len(results)]
            cur_prompt = all_prompts[idx]

            # 1. Replace placeholders if present
            updated_prompt, was_replaced = TagFormatter.replace_placeholders(
                cur_prompt, card.post, fmt_config
            )

            # 2. If no placeholders and Auto-Gacha is enabled
            if not was_replaced and auto_gacha_chk:
                tag_string = card.full_prompt
                if auto_mode_dropdown == "Append to Prompt":
                    updated_prompt = f"{cur_prompt}, {tag_string}".strip(", ")
                elif auto_mode_dropdown == "Prepend to Prompt":
                    updated_prompt = f"{tag_string}, {cur_prompt}".strip(", ")
                elif auto_mode_dropdown == "Replace Full Prompt":
                    updated_prompt = tag_string
                elif auto_mode_dropdown == "Replace [gacha...] placeholders":
                    updated_prompt = f"{cur_prompt}, {tag_string}".strip(", ")

            all_prompts[idx] = updated_prompt

            if auto_neg_chk and exc_tags:
                cur_neg = all_neg_prompts[idx]
                all_neg_prompts[idx] = f"{cur_neg}, {exc_tags}".strip(", ")

        p.prompt = all_prompts[0]
        p.all_prompts = all_prompts

        if auto_neg_chk and exc_tags:
            p.negative_prompt = all_neg_prompts[0]
            p.all_negative_prompts = all_neg_prompts


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
            "",
            "Universal Tag Blacklist",
            gr.Textbox,
        ).info("Comma-separated tags to always exclude from all rolls (e.g. nsfw, watermark, logo, bad anatomy)."),
    }

    for key, opt in gpr_options.items():
        opt.section = GPR_SECTION
        shared.opts.add_option(key, opt)


script_callbacks.on_ui_settings(on_ui_settings)
