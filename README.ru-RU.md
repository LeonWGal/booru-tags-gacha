# Booru Tags Gacha

[![Platform](https://img.shields.io/badge/Platform-SD--WebUI%20%7C%20Forge%20Neo-blue?style=flat-square)](https://github.com/LeonWGal/booru-tags-gacha)
[![Gradio](https://img.shields.io/badge/Gradio-4.x%20%2F%205.x-orange?style=flat-square)](https://gradio.app/)
[![Theme](https://img.shields.io/badge/Theme-Native%20%7C%20Lobe%20Theme-purple?style=flat-square)](https://github.com/LeonWGal/booru-tags-gacha)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](./LICENSE)

Рандомизатор буру-тегов, гача-движок мульти-роллов и инструмент сборки промптов для **Stable Diffusion WebUI** и **Forge Neo** (Gradio 4+).

---

## Содержание
- [Возможности](#возможности)
- [Поддерживаемые буру](#поддерживаемые-буру)
- [Плейсхолдеры промпта](#плейсхолдеры-промпта)
- [Адаптивный интерфейс и темы](#адаптивный-интерфейс-и-темы)
- [Установка](#установка)
- [Настройки и API ключи](#настройки-и-api-ключи)
- [Лицензия](#лицензия)

---

## Возможности

- **Мульти-пулл гача (1x, 5x, 10x)**: Одиночные роллы и паки карт с динамическим расчетом редкости по оценкам и избранному (**UR**, **SSR**, **SR**, **R**, **N**).
- **Universal Tag Classifier**: Автоматическое распознавание и распределение тегов по категориям `Artist`, `Character`, `Series / Copyright`, `General` и `Meta` для всех поддерживаемых буру через пакетные запросы и эвристику.
- **Плейсхолдеры и Auto-Gacha**: Поддержка токенов (`[gacha]`, `[gacha-wa]`, `[gacha-oa]`, `[gacha-oc]`, `[gacha-gen]`, `[gacha-all]`) с автоматической подстановкой при пакетной генерации.
- **Безопасное форматирование эмодзи**: Замена подчеркиваний на пробелы с сохранением текстовых смайлов (`^_^`, `>_<`, `o_o`, `0_0`, `=_=`, `@_@` и др.) и экранирование скобок `\(` `\)`.
- **Встроенный браузер Избранного**: Сохранение понравившихся карточек с метаданными, просмотр промптов и быстрая вставка в позитивный или негативный промпт.
- **Адаптивный визуал**: Солидный контрастный интерфейс в стандартном Gradio / Forge Neo и автоматическое включение glassmorphism, токенов Ant Design и голографических эффектов при активной **Lobe Theme Neo**.

---

## Поддерживаемые буру

| Сервис | Движок | Категоризация тегов | Фильтр рейтинга | Авторизация |
| :--- | :--- | :---: | :---: | :---: |
| **Danbooru** | Danbooru JSON | Нативная | Safe, Sensitive, Questionable, Explicit | Username + API Key |
| **AIBooru (AI Art)** | Danbooru JSON | Нативная | Safe, Sensitive, Questionable, Explicit | Username + API Key |
| **Yande.re** | Moebooru JSON | Universal Classifier | Safe, Questionable, Explicit | Не требуется |
| **Konachan** | Moebooru JSON | Universal Classifier | Safe, Questionable, Explicit | Не требуется |
| **Gelbooru** | Gelbooru DAPI | Universal Classifier | General, Sensitive, Questionable, Explicit | API Key + User ID |
| **Rule34** | Gelbooru DAPI | Universal Classifier | General, Sensitive, Questionable, Explicit | API Key + User ID |
| **Safebooru** | Gelbooru DAPI | Universal Classifier | Safe only | Не требуется |
| **e621 / e926** | e621 JSON | Нативная | Safe, Questionable, Explicit | Username + API Key |
| **Derpibooru** | Philomena JSON | Universal Classifier | Safe, Suggestive, Questionable, Explicit | API Key |
| **Custom Booru** | Настраиваемый | Universal Classifier | Настраиваемый | Настраиваемый |

---

## Плейсхолдеры промпта

Плейсхолдеры можно вставлять напрямую в поле промпта. При генерации они заменяются на выпавшие теги:

| Плейсхолдер | Режим | Содержимое |
| :--- | :--- | :--- |
| `[gacha]` | **Полный промпт** | Все включенные категории тегов по настройкам форматирования |
| `[gacha-wa]` | **Без художника** | Персонаж + Франшиза + Общие + Мета (без тегов автора) |
| `[gacha-oa]` | **Только художник** | Тег автора с выбранным стилем форматирования (`by`, `artist:`, вес) |
| `[gacha-oc]` | **Только персонаж** | Теги персонажей |
| `[gacha-gen]` | **Только общие теги** | Теги окружения, внешности и позы |
| `[gacha-all]` | **Все теги сырыми** | Все теги поста без фильтрации по категориям |

### Пример использования:
```text
masterpiece, best quality, [gacha-oa], 1girl, [gacha-wa], highly detailed background
```

---

## Адаптивный интерфейс и темы

- **Vanilla Gradio / Forge Neo**: Солидные контрастные элементы без нагрузки от `backdrop-filter`, мгновенная отрисовка и стабильность.
- **Lobe Theme Neo**: Автоматическое подключение стилей Lobe Theme (`backdrop-blur`), токенов скруглений Ant Design, карточек редкостей и голографического блеска для UR/SSR.
- **Изоляция SVG**: Защита от сброса стилей Tailwind CSS, предотвращающая растягивание иконок и окон превью.

---

## Установка

### Через вкладку Extensions в WebUI / Forge
1. Откройте Stable Diffusion WebUI / Forge Neo.
2. Перейдите во вкладку **Extensions** → **Install from URL**.
3. Вставьте ссылку: `https://github.com/LeonWGal/booru-tags-gacha.git`
4. Нажмите **Install** и перезапустите интерфейс.

### Ручная установка
```bash
cd extensions
git clone https://github.com/LeonWGal/booru-tags-gacha.git
```

Зависимости (`aiohttp`, `nest_asyncio`) устанавливаются автоматически через `install.py`.

---

## Настройки и API ключи

Перейдите в **Settings** → **Booru Tags Gacha** для настройки учетных записей:

- **Danbooru**: Username + API Key ([Профиль Danbooru](https://danbooru.donmai.us/profile))
- **Gelbooru**: API Key + User ID ([Настройки Gelbooru](https://gelbooru.com/index.php?page=account&s=options))
- **Rule34**: API Key + User ID ([Настройки Rule34](https://rule34.xxx/index.php?page=account&s=options))
- **e621 / e926**: Username + API Key ([Ключи e621](https://e621.net/users/home))
- **Derpibooru**: API Key ([Профиль Derpibooru](https://derpibooru.org/users/edit))
- **Universal Tag Blacklist**: Список тегов через запятую для постоянного исключения из всех роллов.

---

## Лицензия

Проект распространяется под лицензией [MIT License](./LICENSE).
