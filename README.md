# Waterpark Simulator – Locale Text Override Patch

## Overview

This repository provides a **small, optional localization override patch** for *Waterpark Simulator*.

The patch allows players to **replace a specific in-game localized text string** used on certain staff-only objects with a neutral alternative (e.g. `STAFF ONLY`), independent of the game’s active language or localization fallback.

No gameplay mechanics, assets, models, or textures are modified.

---

## What this patch does

* Overrides **one localized string entry** in the game’s localization data
* The patch operates on the game’s localization asset (resources.assets) by replacing a single UTF-8 string with equal byte length.
* Affects **signage text only**
* Keeps the change:

  * minimal
  * reversible
  * binary-safe (byte-length preserved)
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

Some players prefer consistent or neutral signage text regardless of localization or fallback behavior.

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
