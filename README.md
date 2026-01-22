# Waterpark Simulator – Locale Text Override Patch

## Overview

This repository provides a **small, optional localization override patch** for *Waterpark Simulator*.

The patch applies **per-key localization overrides** (via `key_map.json`) to fix specific signage text, independent of the game’s active language or localization fallback.

No gameplay mechanics, assets, models, or textures are modified.

---

## Tools

* `patch_staff_only.py`: end-user patcher that applies `key_map.json` (byte-length preserved)
* `inspect_assets.py`: developer/diagnostic tool for dump/search/list operations (optional language-order fix)

Quick inspect example:

```bash
python3 inspect_assets.py --dump-key "Attractions/StaffOnlySign"
```

---

## What this patch does

* Overrides **specific localized string entries** listed in `key_map.json`
* Preserves **byte length** for in-place, binary-safe edits
* Affects **signage text only** (current map)
* Keeps the change:

  * minimal
  * reversible
  * deterministic
* Does **not** modify:

  * gameplay
  * progression
  * save files
  * multiplayer logic

---

## What this patch does *not* do

* It does **not** add or remove languages
* It does **not** change global localization settings
* It does **not** include original game files
* It does **not** modify textures or models
* It does **not** affect performance or stability

---

## Why this exists

Some players prefer consistent or corrected signage text regardless of localization or fallback behavior.

This patch exists solely to provide **player choice** in how that specific text is displayed.

---

## Installation (summary)

* Requires a **legitimate copy** of *Waterpark Simulator*
* Applies a small binary-safe modification to the localization asset
* Instructions are provided in `/docs/INSTALL.md`

> Always back up original files before applying any patch.

---

## Compatibility

* Game updates may overwrite patched files
* Re-application may be required after updates
* Tested on the current Steam version at time of release

---

## Disclaimer

This project is **not affiliated with or endorsed by** the developers or publisher of *Waterpark Simulator*.

All trademarks and copyrights belong to their respective owners.

---

## License

This repository contains **only original patching scripts and documentation**.
No copyrighted game assets are distributed.

---

## Support

This patch is provided **as-is**.
No guarantees, no official support, no update promises.

---

If you prefer not to modify your game files, simply do not use this patch.
