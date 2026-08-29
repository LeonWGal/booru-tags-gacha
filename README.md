# 🎲 Booru Tags Gacha 2.0

[![Forge Neo](https://img.shields.io/badge/Platform-Forge%20Neo%20%7C%20SD--WebUI-blue?style=for-the-badge)](https://github.com/Haoming02/sd-webui-forge-classic)
[![Gradio 4](https://img.shields.io/badge/UI-Gradio%204+-orange?style=for-the-badge)](https://gradio.app/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)

A high-performance, next-generation Booru tag randomizer, multi-pull gacha engine, and prompt engineering tool designed for **Stable Diffusion WebUI** and **Forge Neo** with native **Gradio 4+** support.

[🇷🇺 Читать документацию на русском языке (README.ru-RU.md)](./README.ru-RU.md)

---

## 📑 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [Supported Booru Engines](#-supported-booru-engines)
- [Prompt Placeholders & Gacha Syntax](#-prompt-placeholders--gacha-syntax)
- [UI & UX Highlights](#-ui--ux-highlights)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Architecture & Extensibility](#-architecture--extensibility)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [License](#-license)

---

## 🌟 Overview

**Booru Tags Gacha 2.0** brings the excitement of gacha mechanics and the precision of modern Booru APIs directly into your Stable Diffusion workflow. Whether you want to pull random artist aesthetics, discover character concepts, or continuously randomize tags on every generation, this extension provides full control over tag categories, prompt formatting, weights, and filtering.

---

## ✨ Key Features

- **🌐 Multi-Engine Architecture**: Native JSON and XML API adapters for Danbooru, Gelbooru, Moebooru (Yande.re, Konachan), e621, Philomena (Derpibooru), AIBooru, and custom boorus.
- **🎰 Multi-Pull Gacha (1x, 5x, 10x)**: Roll single cards or multi-pull packs (5x Lucky Roll, 10x SSR Pull) with dynamic rarity badges calculated from post scores and favorites (**UR 💎**, **SSR 🌟**, **SR ✨**, **R 🔷**, **N ⚪**).
- **🏷️ Tag Categorization & Filtering**: Full category control across `Artist`, `Character`, `Copyright / Series`, `General`, and `Meta` tags with instant toggle checkboxes.
- **🛡️ Emoticon-Safe Underscore Replacement**: Converts underscores `_` to spaces without breaking text emoticons (`^_^`, `>_<`, `o_o`, `0_0`, `=_=`, `@_@`, `u_u`, `x_x`, `3_3`, `6_9`, `>_o`, etc.).
- **🔒 Automatic SD Parenthesis Escaping**: Automatically escapes parentheses `\(` and `\)` in character and franchise names (e.g. `rem \(re:zero\)`) to prevent unintentional prompt weighting in WebUI.
- **⚡ Prompt Placeholders & Auto-Gacha**: Seamless placeholder substitution (`[gacha]`, `[gacha-wa]`, `[gacha-oa]`, `[gacha-oc]`, `[gacha-gen]`, `[gacha-all]`) and continuous per-batch auto-rolling.
- **💾 Presets & Persistent Favorites**: Save your favourite rolls into `gacha_favorites.json`, create custom named search presets, and browse session roll history with `◀ Prev` and `Next ▶`.

---

## 🌐 Supported Booru Engines

| Engine / Site | API Type | Tag Categorization | Rating Filter | Min Score | Auth Support |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Danbooru** | JSON | ✅ Full | ✅ `g`, `s`, `q`, `e` | ✅ | Username + API Key |
| **AIBooru (AI Art)** | JSON | ✅ Full | ✅ `g`, `s`, `q`, `e` | ✅ | Username + API Key |
| **Yande.re (Moebooru)** | JSON | ✅ Full | ✅ `s`, `q`, `e` | ✅ | None required |
| **Konachan** | JSON | ✅ Full | ✅ `s`, `q`, `e` | ✅ | None required |
| **Gelbooru** | JSON / XML | ✅ Full | ✅ `general`, `sensitive`, `questionable`, `explicit` | ✅ | API Key + User ID |
| **Rule34** | JSON / XML | ✅ Full | ✅ `general`, `sensitive`, `questionable`, `explicit` | ✅ | API Key + User ID |
| **Safebooru** | JSON / XML | ✅ Full | ✅ Safe only | ✅ | None required |
| **e621 / e926** | JSON | ✅ Full (Species, Lore, Meta, Artist, Char) | ✅ `s`, `q`, `e` | ✅ | Username + API Key |
| **Derpibooru (Philomena)** | JSON | ✅ Full | ✅ `safe`, `suggestive`, `questionable`, `explicit` | ✅ | API Key |
| **Custom Booru** | Multi-Engine | ✅ Configurable | ✅ Configurable | ✅ | Configurable |

---

## 🎯 Prompt Placeholders & Gacha Syntax

You can insert dedicated placeholder tokens directly into your prompt or negative prompt. When generation starts (or when clicking prompt injection buttons), the placeholders are automatically populated with the corresponding tag subset:

| Placeholder | Name | Description | Example Output |
| :--- | :--- | :--- | :--- |
| `[gacha]` | **Full Roll** | Inserts all enabled categories based on active formatting settings. | `by citemoca, rem \(re:zero\), 1girl, blue hair, maid outfit` |
| `[gacha-wa]` | **Without Artist** | Inserts character, franchise, and general tags, but **excludes** artist tags. | `rem \(re:zero\), 1girl, blue hair, maid outfit, sitting` |
| `[gacha-oa]` | **Only Artist** | Inserts **only** the artist tag(s) with selected artist formatting. | `by citemoca` or `artist:citemoca` |
| `[gacha-oc]` | **Only Character** | Inserts **only** character tag(s). | `rem \(re:zero\), ram \(re:zero\)` |
| `[gacha-gen]` | **Only General** | Inserts **only** general subject and environmental tags. | `1girl, blue hair, maid outfit, sitting` |
| `[gacha-all]` | **All Raw Tags** | Inserts all raw tags without category exclusions. | `citemoca, rem, 1girl, blue_hair, highres, absurdres` |

### 💡 Example Prompt Recipes

```text
# Split artist and character placement
masterpiece, best quality, [gacha-oa], 1girl, solo, [gacha-wa], highly detailed background, cinematic lighting

# Character-only roll with your own artist styles
masterpiece, 8k wallpaper, [gacha-oc], by wlop, by artgerm, dynamic pose

# Pure aesthetic exploration
[gacha], masterpiece, absurdres, volumetric lighting
```

---

## 🎨 UI & UX Highlights

```
+-------------------------------------------------------------------------+
| 🎲 Booru Tags Gacha                                                     |
| Preset: [ 🌸 Anime Solo Girl ▼ ]  [ 💾 Save ]  [ ➕ New ]  [ 🗑️ Delete ]  |
+-------------------------------------------------------------------------+
| Site: [ Danbooru ▼ ]   Rating: [ safe ▼ ]   Min Score: [ 20 ]           |
| Include: [ 1girl, solo, scenic                                        ] |
| Exclude: [ censored, text, watermark, bad anatomy                     ] |
+-------------------------------------------------------------------------+
| [ 🎲 1x Roll ]      [ 🎰 5x Lucky Roll ]      [ 💎 10x Pull (SSR) ]     |
+-------------------------------------------------------------------------+
|  [ Preview Image ]   |  [ Gacha Multi-Pull Card Gallery ]               |
|  💎 UR ⭐⭐⭐⭐⭐    |  - Card 1: 🌟 SSR (Score: 184)                   |
|  Score: 195          |  - Card 2: 💎 UR  (Score: 320)                   |
|  Rating: Safe        |  - Card 3: ✨ SR  (Score: 54)                    |
+-------------------------------------------------------------------------+
| Formatted Tags: [ by citemoca, rem \(re:zero\), 1girl, blue hair...   ] |
| Artist: [ citemoca ]  Char: [ rem (re:zero) ]  Series: [ re:zero ]      |
+-------------------------------------------------------------------------+
| [ ➕ Append ]  [ 🔄 Replace ]  [ ⬆️ Prepend ]  [ ⛔ To Negative ]         |
| [ 🎨 Artist Only ]  [ 👤 Char Only ]  [ ⭐ Save to Favorites ]          |
+-------------------------------------------------------------------------+
| ⚙️ Advanced Tag Formatting & Category Options (Collapsible)             |
| ⚡ Auto-Gacha on Generate (Script Mode) (Collapsible)                    |
+-------------------------------------------------------------------------+
```

---

## 🚀 Installation

### Via WebUI / Forge Extensions Tab
1. Open Stable Diffusion WebUI / Forge Neo.
2. Navigate to **Extensions** → **Install from URL**.
3. Paste repository URL: `https://github.com/Haoming02/sd-webui-forge-classic` (or your fork).
4. Click **Install** and restart the WebUI.

### Manual Installation
Clone this repository into your extensions directory:
```bash
cd extensions
git clone https://github.com/Haoming02/sd-webui-forge-classic.git booru-tags-gacha
```

Dependencies (`aiohttp`, `nest_asyncio`) are managed automatically via `install.py`.

---

## ⚙️ Configuration

Go to **Settings** → **Booru Tags Gacha** to configure API keys:

- **Danbooru**: Username + API Key ([Danbooru Profile](https://danbooru.donmai.us/profile))
- **Gelbooru**: API Key + User ID ([Gelbooru Options](https://gelbooru.com/index.php?page=account&s=options))
- **Rule34**: API Key + User ID ([Rule34 Options](https://rule34.xxx/index.php?page=account&s=options))
- **e621 / e926**: Username + API Key ([e621 API Access](https://e621.net/users/home))
- **Derpibooru**: API Key ([Derpibooru Account](https://derpibooru.org/users/edit))
- **Custom Booru**: Base URL, backend engine type, API key, and user credentials.
- **Universal Tag Blacklist**: Comma-separated list of tags to exclude from every roll (e.g. `nsfw, watermark, logo, text, bad anatomy`).

---

## 🏛️ Architecture & Extensibility

```
booru-tags-gacha/
├── install.py                  # Auto-dependency installer
├── style.css                   # Gradio 4 modern CSS themes and badge styles
├── gacha_presets.json          # Persistent user presets
├── gacha_favorites.json        # Persistent favorited rolls
├── README.md                   # English documentation
├── README.ru-RU.md             # Russian documentation
└── scripts/
    ├── BooruTagsGacha.py       # Main WebUI Script & Gradio 4 UI Layout
    └── boorus/
        ├── __init__.py         # Registry and engine factory
        ├── base.py             # BooruPost, BooruClient base models
        ├── formatter.py        # Advanced tag formatting, emoticons, placeholders
        ├── gacha.py            # Multi-pull async engine & rarity calculation
        ├── presets.py          # Presets CRUD and legacy migration
        ├── favorites.py        # Persistent favorites and roll history
        ├── danbooru.py         # Danbooru JSON engine
        ├── aibooru.py          # AIBooru AI-art engine
        ├── moebooru.py         # Yande.re & Konachan engine
        ├── gelbooru.py         # Gelbooru / Rule34 / Safebooru DAPI engine
        ├── e621.py             # e621 / e926 engine
        ├── philomena.py        # Derpibooru engine
        └── custom.py           # Universal configurable engine adapter
```

---

## ❓ Troubleshooting & FAQ

#### Q: Danbooru returns 403 or blocked responses?
> **A:** Danbooru uses Cloudflare bot protection. Booru Tags Gacha uses compliant browser headers. If issues persist, configure your Danbooru Username and API key in Settings.

#### Q: Emoticons like `>_<` or `^_^` were broken in other extensions. How is it handled here?
> **A:** Booru Tags Gacha includes a protected emoticon lookup table that safeguards smileys and emotes from underscore-to-space replacement.

#### Q: Can I use Auto-Gacha with batch generation (`batch_size` / `n_iter`)?
> **A:** Yes! When enabled, the script rolls distinct posts for every image in the batch, allowing high-throughput prompt exploration.

---

## 📄 License

Distributed under the [MIT License](./LICENSE).
