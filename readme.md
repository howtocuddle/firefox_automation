# Firefox Automation (Browser Tool)

## Overview

This repository contains a **robust, modular browser automation toolkit** built on top of Selenium and Gemini Vision. It provides high‑level actions that mimic human interaction while handling edge‑cases such as hidden elements, shadow DOMs, Cloudflare challenges, and multi‑tab workflows.

## Key Features

- **Open in New Tab (`OPEN_IN_NEW_TAB`)** – Opens links via `window.open(href)` when possible, falls back to `Ctrl+Click`.
- **Robust Interaction Primitives**
  - `click`, `hover`, `focus`, `right_click` – Coordinate‑first strategy with JavaScript fallback.
  - **State‑Change Detection** – Captures element attributes before and after interaction; reports detailed changes (e.g., `aria-label: 'Play' → 'Pause'`).
  - **Human‑type (`human_type`)** – Handles hidden or tiny inputs by directly sending keys.
- **Cloudflare & CAPTCHA Handling** – Heuristic detection and graceful waiting for resolution.
- **Semantic Object Model (SoM) Enhancements** – Improved element detection, including search bars, forms, and shadow DOM elements.
- **Navigation Helpers** – `visit`, `new_tab`, automatic protocol prefixing.
- **Research Mode** – Multi‑tab support (optional) for deep research tasks.
- **Extensible Architecture** – Easy to add new actions via `actions.py` and expose them in `autonomous.py`.

## Architecture

```
src/tools/browser/
│   actions.py          # Core action implementations (click, hover, open_in_new_tab, …)
│   autonomous.py       # Agent loop, system prompt, command parsing
│   navigation.py       # URL handling, tab management
│   helpers.py          # Utility functions, OCR, CAPTCHA handling
│   research.py         # High‑level research workflow (multi‑tab)
│   verify_context.py   # Context verification utilities
│   xpath_journal.py    # Caching of generated XPaths
│   browser_som.js      # JavaScript for Semantic Object Model extraction
│   browser_content.js  # Helper JS injected into pages
│   config.py           # Configuration (profile paths, binaries, etc.)
│   ...
```

- **`actions.py`** implements the public actions exposed to the LLM. Each action logs detailed feedback used by the autonomous loop.
- **`autonomous.py`** contains the main loop, system prompt, and command dispatcher. It decides when to use research vs. execution mode.
- **`navigation.py`** normalises URLs and handles tab creation/switching.
- **`helpers.py`** provides OCR, Cloudflare detection, and generic utilities.
- **`browser_som.js`** runs in the browser to collect element metadata for robust detection.

## Getting Started

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure** `config.py` – set `BROWSER_PROFILE_PATH` and `BROWSER_BINARY_LOCATION`.
3. **Run tests**
   ```bash
   python -m pytest tests/
   ```
4. **Use the agent** – invoke `autonomous.py` or integrate the actions via the provided API.

## Contributing

- Follow the existing code style.
- Add new actions in `actions.py` and expose them in `autonomous.py`.
- Update the system prompt in `autonomous.py` when adding capabilities.
- Ensure tests cover new functionality.

## License

MIT License – see `LICENSE` file.
