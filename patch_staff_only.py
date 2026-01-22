#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time
from typing import Iterable, List

GAME_DIR_NAME = "WaterPark Simulator"
DATA_SUBDIR = "WaterparkSimulator_Data"
ASSETS_FILE = "resources.assets"

OLD_TEXT = "ТОЛЬКО ПЕРСОНАЛ"
DEFAULT_NEW_TEXT = "STAFF ONLY"


def _pad_bytes(new_bytes: bytes, target_len: int) -> bytes:
    if len(new_bytes) > target_len:
        raise ValueError("Replacement text is longer than the original.")
    return new_bytes + (b" " * (target_len - len(new_bytes)))


def _unique_backup_path(path: pathlib.Path) -> pathlib.Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(path.name + f".bak_{stamp}")
    if not candidate.exists():
        return candidate
    for i in range(1, 1000):
        candidate = path.with_name(path.name + f".bak_{stamp}_{i}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Unable to create a unique backup filename.")


def _parse_libraryfolders(vdf_path: pathlib.Path) -> List[str]:
    if not vdf_path.exists():
        return []
    text = vdf_path.read_text(encoding="utf-8", errors="ignore")
    return [match.group(1) for match in re.finditer(r"\"path\"\\s+\"([^\"]+)\"", text)]


def _normalize_library_path(raw: str) -> str:
    if os.name == "nt":
        return raw.replace("\\\\", "\\")
    return raw


def _default_steamapps_dirs() -> List[pathlib.Path]:
    home = pathlib.Path.home()
    candidates = []
    if os.name == "nt":
        for env_key in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env_key)
            if base:
                candidates.append(pathlib.Path(base) / "Steam" / "steamapps")
    else:
        candidates.extend(
            [
                home / ".local/share/Steam/steamapps",
                home / ".steam/steam/steamapps",
                home / ".steam/root/steamapps",
            ]
        )
    env_dir = os.environ.get("STEAMAPPS_DIR")
    if env_dir:
        candidates.append(pathlib.Path(env_dir).expanduser())
    return candidates


def _discover_library_paths() -> List[pathlib.Path]:
    libraries: List[pathlib.Path] = []
    for steamapps in _default_steamapps_dirs():
        if not steamapps.exists():
            continue
        libraries.append(steamapps.parent)
        vdf_path = steamapps / "libraryfolders.vdf"
        for raw in _parse_libraryfolders(vdf_path):
            path = pathlib.Path(_normalize_library_path(raw))
            if path.exists():
                libraries.append(path)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for lib in libraries:
        key = str(lib.resolve()) if lib.exists() else str(lib)
        if key in seen:
            continue
        seen.add(key)
        unique.append(lib)
    return unique


def _find_game_dirs(libraries: Iterable[pathlib.Path]) -> List[pathlib.Path]:
    matches: List[pathlib.Path] = []
    for lib in libraries:
        common = lib / "steamapps" / "common"
        if not common.exists():
            continue
        direct = common / GAME_DIR_NAME
        if direct.exists():
            matches.append(direct)
            continue
        for child in common.iterdir():
            if child.is_dir() and child.name.casefold() == GAME_DIR_NAME.casefold():
                matches.append(child)
    return matches


def _resolve_assets_path(game_dir: pathlib.Path) -> pathlib.Path:
    return game_dir / DATA_SUBDIR / ASSETS_FILE


def _patch_assets(assets_path: pathlib.Path, new_text: str, dry_run: bool) -> int:
    data = assets_path.read_bytes()
    old_bytes = OLD_TEXT.encode("utf-8")
    new_bytes = new_text.encode("utf-8")
    new_padded = _pad_bytes(new_bytes, len(old_bytes))

    old_count = data.count(old_bytes)
    if old_count == 0:
        if new_padded in data:
            print("Already patched.")
            return 0
        print("ERROR: Target string not found. The game may have updated assets.")
        return 3
    if old_count != 1:
        print(f"ERROR: Unexpected occurrence count: {old_count}")
        return 4

    if dry_run:
        print("Dry run OK: patch would be applied.")
        return 0

    backup_path = _unique_backup_path(assets_path)
    backup_path.write_bytes(data)

    patched = data.replace(old_bytes, new_padded, 1)
    assets_path.write_bytes(patched)

    if len(patched) != len(data):
        print("WARNING: File size changed unexpectedly.")
    if patched.count(new_padded) != 1:
        print("WARNING: Replacement count unexpected.")

    print("Patched successfully.")
    print(f"Backup: {backup_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch RU 'ТОЛЬКО ПЕРСОНАЛ' to a custom string in WaterPark Simulator."
    )
    parser.add_argument(
        "--game-dir",
        default=None,
        help="Steam game install dir. If omitted, auto-detects from Steam libraries.",
    )
    parser.add_argument(
        "--assets-path",
        default=None,
        help="Direct path to resources.assets (overrides --game-dir).",
    )
    parser.add_argument(
        "--text",
        default=DEFAULT_NEW_TEXT,
        help="Replacement text (UTF-8). Default: STAFF ONLY",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List detected game directories and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check only; do not write changes.",
    )
    args = parser.parse_args()

    if args.assets_path:
        assets_path = pathlib.Path(args.assets_path).expanduser().resolve()
        if not assets_path.exists():
            print(f"ERROR: resources.assets not found at: {assets_path}")
            return 2
        return _patch_assets(assets_path, args.text, args.dry_run)

    if args.game_dir:
        game_dir = pathlib.Path(args.game_dir).expanduser().resolve()
        assets_path = _resolve_assets_path(game_dir)
        if not assets_path.exists():
            print(f"ERROR: resources.assets not found at: {assets_path}")
            return 2
        return _patch_assets(assets_path, args.text, args.dry_run)

    libraries = _discover_library_paths()
    game_dirs = _find_game_dirs(libraries)

    if args.list:
        if not game_dirs:
            print("No game directories found.")
            return 1
        for path in game_dirs:
            print(path)
        return 0

    if not game_dirs:
        print("ERROR: Game directory not found. Use --game-dir or --assets-path.")
        return 1
    if len(game_dirs) > 1:
        print("ERROR: Multiple game directories found. Use --game-dir to choose.")
        for path in game_dirs:
            print(f" - {path}")
        return 1

    assets_path = _resolve_assets_path(game_dirs[0])
    if not assets_path.exists():
        print(f"ERROR: resources.assets not found at: {assets_path}")
        return 2

    return _patch_assets(assets_path, args.text, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
