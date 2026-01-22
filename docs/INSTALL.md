# Installation

## Requirements

* Python **3.8+**
* A **legitimate Steam installation** of *Waterpark Simulator*
* Basic familiarity with command-line usage

---

## Quick start

From the repository root directory:

### Linux / Steam (Proton)

```bash
python3 patch_staff_only.py
```

### Windows (PowerShell)

```powershell
python patch_staff_only.py
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

## Options

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

### Custom replacement text

```bash
python3 patch_staff_only.py --text "NUR PERSONAL"
```

Notes:

* The replacement text must be **equal to or shorter** than the original localized string.
* The patcher will automatically pad the string to preserve binary safety.

---

## Notes

* A **timestamped backup** of `resources.assets` is created automatically.
* Steam updates or **"Verify integrity of game files"** may overwrite patched files.

  * If this happens, simply re-run the patcher.
* This patch modifies **only one localized string** inside the localization asset.

---

## Uninstall / Revert

To revert changes:

* Restore the backup file created next to `resources.assets`, or
* Verify game files via Steam to restore the original asset.
