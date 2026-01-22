# Installation

## Requirements

* Python **3.8+**
* A **legitimate Steam installation** of *Waterpark Simulator*
* Basic familiarity with command-line usage

---

## Quick start

From the repository root directory (uses `key_map.json` by default):

### Linux / Steam (Proton)

```bash
python3 patch_staff_only.py
```

### Windows (PowerShell)

```powershell
python patch_staff_only.py
```

---

## One-click launchers (optional)

### Linux

```bash
./run.sh
```

If needed:
```bash
chmod +x run.sh
```

### Windows

Double-click `run.bat`, or run:
```powershell
run.bat
```

---

## Manual game path (optional)

If automatic detection fails, explicitly pass the game directory.

### Linux

```bash
python3 patch_staff_only.py --game-dir "$HOME/.local/share/Steam/steamapps/common/WaterPark Simulator"
```

### Windows

```powershell
python patch_staff_only.py --game-dir "C:\Program Files (x86)\Steam\steamapps\common\WaterPark Simulator"
```

---

## Options (patcher)

### List detected installations

```bash
python3 patch_staff_only.py --list
```

---

### Dry run (no changes written)

```bash
python3 patch_staff_only.py --dry-run
```

Use this to verify detection and patch targets before modifying any files.

---

### Custom key map

```bash
python3 patch_staff_only.py --key-map ./key_map.json
```

---

## Key map format

Create a JSON file that maps keys to language codes:

```json
{
  "Attractions/StaffOnlySign": {
    "es": "SOLO PERS.",
    "fr": "PERSONNEL",
    "de": "NUR PERSONAL"
  }
}
```

Run:

```bash
python3 patch_staff_only.py --key-map ./key_map.json --dry-run
python3 patch_staff_only.py --key-map ./key_map.json
```

Notes:

* Replacement text must be **equal to or shorter** than the existing string for that language.
* The patcher pads values to preserve byte length and file size.

---

## Inspection tool (inspect_assets.py)

Use this tool for diagnostics and analysis. It does not modify files unless you use the
language-order fix option.

### List language sources

```bash
python3 inspect_assets.py --list-language-sources
```

---

### Dump a localization key

```bash
python3 inspect_assets.py --dump-key "Attractions/StaffOnlySign"
```

If multiple language sources exist, add `--language-source-index`.

---

### Search for a translation or key

Find keys by a text fragment:

```bash
python3 inspect_assets.py --search-text "container" --search-ignore-case
```

Find keys by key name:

```bash
python3 inspect_assets.py --search-key "Trash" --search-ignore-case
```

Use `--search-all-keys` to include keys without `/`.

---

### Diagnostic: fix language order

Use only if you know the asset has an incorrect language column order.

```bash
python3 inspect_assets.py --fix-language-order --dry-run
```

Fix a specific source:

```bash
python3 inspect_assets.py --fix-language-order --language-source-index 0 --dry-run
python3 inspect_assets.py --fix-language-order --language-source-index 0
```

Fix all matching sources:

```bash
python3 inspect_assets.py --fix-language-order --fix-all-language-sources --dry-run
```

Optional: custom order (comma-separated codes):

```bash
python3 inspect_assets.py --fix-language-order --language-order "en,es,fr,uk,ru,de,pt,zh-CN,zh-TW,ja,ko,it,vi,pl"
```

---

## Notes

* A **timestamped backup** of `resources.assets` is created automatically.
* Steam updates or **"Verify integrity of game files"** may overwrite patched files.

  * If this happens, simply re-run the patcher.
* This patch modifies **one or more localized strings** inside the localization asset.

---

## Uninstall / Revert

To revert changes:

* Restore the backup file created next to `resources.assets`, or
* Verify game files via Steam to restore the original asset.
