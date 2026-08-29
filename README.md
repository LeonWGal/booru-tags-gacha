# 🎲 Booru Tags Gacha

[![Platform](https://img.shields.io/badge/Platform-SD--WebUI%20%7C%20Forge%20Neo-blue?style=flat-square)](https://github.com/LeonWGal/booru-tags-gacha)
[![Gradio](https://img.shields.io/badge/Gradio-4.x%20%2F%205.x-orange?style=flat-square)](https://gradio.app/)
[![Theme](https://img.shields.io/badge/Theme-Native%20%7C%20Lobe%20Theme-purple?style=flat-square)](https://github.com/LeonWGal/booru-tags-gacha)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](./LICENSE)

Booru tag randomizer, multi-pull gacha engine, and prompt formatter for **Stable Diffusion WebUI** and **Forge Neo** (Gradio 4+).

[🇷🇺 Документация на русском языке (README.ru-RU.md)](./README.ru-RU.md)

---

## Table of Contents
- [Features](#features)
- [Supported Boorus](#supported-boorus)
- [Prompt Placeholders](#prompt-placeholders)
- [Adaptive UI & Themes](#adaptive-ui--themes)
- [Installation](#installation)
- [Settings & API Keys](#settings--api-keys)
- [License](#license)

---

## Features

- **🎰 Multi-Pull Gacha (1x, 5x, 10x)**: Single roll or multi-card packs with dynamic rarity calculation based on score and favorites (**UR 💎**, **SSR 🌟**, **SR ✨**, **R 🔷**, **N ⚪**).
- **🏷️ Universal Tag Classifier**: Automatically identifies and categorizes tags into `Artist(s)`, `Character(s)`, `Series/Copyright`, `General`, and `Meta` across all supported boorus using batch tag lookups and heuristic detection.
- **⚡ Prompt Placeholders & Auto-Gacha**: Flexible placeholder tokens (`[gacha]`, `[gacha-wa]`, `[gacha-oa]`, `[gacha-oc]`, `[gacha-gen]`, `[gacha-all]`) with support for batch generation replacement.
- **🛡️ Emoticon-Safe Formatter**: Replaces underscores with spaces while preserving face emoticons (`^_^`, `>_<`, `o_o`, `0_0`, `=_=`, `@_@`, etc.) and automatically escapes SD prompt parentheses `\(` `\)`.
- **⭐ Built-in Favorites Explorer**: Save favorite cards with full metadata, inspect saved prompts, and re-inject them into positive or negative prompts anytime.
- **🎨 Adaptive Styling**: Clean, high-contrast solid native Gradio interface by default; seamlessly activates glassmorphism, Ant Design tokens, and holographic badges when **Lobe Theme Neo** is active.

---

## Supported Boorus

| Booru Site | Engine | Tag Classification | Rating Filter | Auth Support |
| :--- | :--- | :---: | :---: | :---: |
| **Danbooru** | Danbooru JSON | Native Categories | Safe, Sensitive, Questionable, Explicit | Username + API Key |
| **AIBooru (AI Art)** | Danbooru JSON | Native Categories | Safe, Sensitive, Questionable, Explicit | Username + API Key |
| **Yande.re** | Moebooru JSON | Universal Classifier | Safe, Questionable, Explicit | Not required |
| **Konachan** | Moebooru JSON | Universal Classifier | Safe, Questionable, Explicit | Not required |
| **Gelbooru** | Gelbooru DAPI | Universal Classifier | General, Sensitive, Questionable, Explicit | API Key + User ID |
| **Rule34** | Gelbooru DAPI | Universal Classifier | General, Sensitive, Questionable, Explicit | API Key + User ID |
| **Safebooru** | Gelbooru DAPI | Universal Classifier | Safe only | Not required |
| **e621 / e926** | e621 JSON | Native Categories | Safe, Questionable, Explicit | Username + API Key |
| **Derpibooru** | Philomena JSON | Universal Classifier | Safe, Suggestive, Questionable, Explicit | API Key |
| **Custom Booru** | Configurable | Universal Classifier | Configurable | Configurable |

---

## Prompt Placeholders

Placeholders can be typed directly into your prompt. During generation (or when using prompt buttons), they are dynamically replaced with the rolled tags:

| Placeholder | Mode | Output Content |
| :--- | :--- | :--- |
| `[gacha]` | **Full Prompt** | Full tag set according to active formatting rules |
| `[gacha-wa]` | **Without Artist** | Character + Series + General + Meta (excludes artist) |
| `[gacha-oa]` | **Only Artist** | Artist tag(s) only with chosen artist format |
| `[gacha-oc]` | **Only Character** | Character tag(s) only |
| `[gacha-gen]` | **Only General** | General subject and environmental tags only |
| `[gacha-all]` | **All Raw Tags** | All unformatted tags from the post |

### Example Usage:
```text
masterpiece, best quality, [gacha-oa], 1girl, [gacha-wa], highly detailed background
```

---

## Adaptive UI & Themes

- **Vanilla Gradio / Forge Neo**: Solid, high-contrast surfaces without `backdrop-filter` overhead, clean layout, and fast render times.
- **Lobe Theme Neo**: Automatic detection enables glassmorphism (`backdrop-blur`), Ant Design token inheritance, card elevation, and holographic shine animations on UR/SSR pulls.
- **SVG / Icon Isolation**: Built-in reset isolation prevents Tailwind CSS and Ant Design from stretching icons or image preview frames.

---

## Installation

### Via WebUI / Forge Extensions Tab
1. Open Stable Diffusion WebUI or Forge Neo.
2. Go to **Extensions** → **Install from URL**.
3. Paste: `https://github.com/LeonWGal/booru-tags-gacha.git`
4. Click **Install** and restart the WebUI.

### Manual Clone
```bash
cd extensions
git clone https://github.com/LeonWGal/booru-tags-gacha.git
```

Dependencies (`aiohttp`, `nest_asyncio`) are installed automatically via `install.py`.

---

## Settings & API Keys

Navigate to **Settings** → **Booru Tags Gacha** to configure optional accounts:

- **Danbooru**: Username + API Key ([Danbooru Profile](https://danbooru.donmai.us/profile))
- **Gelbooru**: API Key + User ID ([Gelbooru Account Options](https://gelbooru.com/index.php?page=account&s=options))
- **Rule34**: API Key + User ID ([Rule34 Options](https://rule34.xxx/index.php?page=account&s=options))
- **e621 / e926**: Username + API Key ([e621 API Keys](https://e621.net/users/home))
- **Derpibooru**: API Key ([Derpibooru Account](https://derpibooru.org/users/edit))
- **Universal Tag Blacklist**: Comma-separated list of tags to exclude across all rolls (e.g. `bad_anatomy, text, watermark`).

---

## License

This project is released under the [MIT License](./LICENSE).
