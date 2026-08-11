# Booru Tags Gacha

Pull tags from a random booru post into your prompt, preview the result, and keep separate saved tab presets for txt2img and img2img.

Russian: [README.ru-RU.md](./README.ru-RU.md)

## Features

- Supports Gelbooru, Rule34, Safebooru, Danbooru, e621, and a custom Gelbooru-DAPI-compatible site.
- Uses Include Tags and Exclude Tags filters when requesting a random post.
- Shows generated tags, artist tags, preview image, and post URL.
- Provides Replace Tags and Append Tags actions for the active prompt.
- Keeps per-tab state in `gpr_tabs.json` with 5 tabs for `txt2img` and 5 tabs for `img2img`.
- Saves tab fields automatically, including a grouped snapshot when `Randomize` runs.
- Supports session history navigation with Previous and Next.
- Offers a universal blacklist and optional underscore-to-space replacement with an exclusion list.

## Installation

1. Place this folder in the WebUI `extensions/` directory as `booru-tags-gacha`.
2. Start or restart the WebUI.
3. On first launch, `install.py` installs required Python packages such as `aiohttp`, `xmltodict`, and `furl`.

## Setup

1. Open Settings and find the `Booru Tags Gacha` section.
2. Enter API credentials for sites that require them.
3. Optionally configure the universal blacklist and underscore replacement exclusion list.
4. Apply settings.

## Usage

1. Open the `Booru Tags Gacha` accordion above sampler settings.
2. Choose a tab, then pick a site and set Include / Exclude tags.
3. Click `Randomize` to fetch a post and extract tags.
4. Use `Replace Tags` or `Append Tags` to send the result into the current prompt.
5. Use `Previous`, `Next`, `Cancel`, or `Clear` as needed.

## Notes

- `gpr_tabs.json` stores the saved site, include, and exclude values for each tab. Seen post IDs are kept only in memory for the current WebUI session.
- Danbooru can return `403` responses because of Cloudflare even with valid credentials.
- e621 credentials are optional, but some content can be filtered without them.
- The custom site option expects a Gelbooru-DAPI-compatible base URL.
- If a dependency is missing after startup, install it in the WebUI environment and restart.

## Customization

Most behavior is configured from Settings. The main script is `scripts/BooruTagsGacha.py`, and per-tab saved state lives in `gpr_tabs.json`.

## Credits

The Gelbooru-DAPI client is based on [PyGelbooru](https://pypi.org/project/pygelbooru/).
