#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

GAME_DIR_NAME = "WaterPark Simulator"
DATA_SUBDIR = "WaterparkSimulator_Data"
ASSETS_FILE = "resources.assets"

DEFAULT_KEY_MAP = "key_map.json"
DEFAULT_LANGUAGE_ORDER = [
    "en",
    "es",
    "fr",
    "uk",
    "ru",
    "de",
    "pt",
    "zh-CN",
    "zh-TW",
    "ja",
    "ko",
    "it",
    "vi",
    "pl",
]


@dataclass(frozen=True)
class LocalizationEntry:
    key: str
    offset: int
    desc: str
    values: List[str]
    spans: List[tuple[int, int]]
    lengths: List[int]


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


def _read_aligned_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of data while reading string length.")
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    end = offset + length
    if end > len(data):
        raise ValueError("Unexpected end of data while reading string payload.")
    text = data[offset:end].decode("utf-8", errors="ignore")
    offset = end
    if offset % 4:
        offset += 4 - (offset % 4)
    return text, offset


def _read_aligned_string_with_span(
    data: bytes, offset: int
) -> tuple[str, int, int, int, int]:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of data while reading string length.")
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    start = offset
    end = start + length
    if end > len(data):
        raise ValueError("Unexpected end of data while reading string payload.")
    text = data[start:end].decode("utf-8", errors="ignore")
    offset = end
    if offset % 4:
        offset += 4 - (offset % 4)
    return text, start, end, length, offset


def _find_occurrences(data: bytes, needle: bytes) -> List[int]:
    positions: List[int] = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index == -1:
            break
        positions.append(index)
        start = index + len(needle)
    return positions


def _find_key_entries_with_spans(
    data: bytes, key: str, language_count: int
) -> List[LocalizationEntry]:
    key_bytes = key.encode("utf-8")
    needle = struct.pack("<I", len(key_bytes)) + key_bytes
    offsets = _find_occurrences(data, needle)
    entries: List[LocalizationEntry] = []

    for start in offsets:
        offset = start + 4 + len(key_bytes)
        if offset % 4:
            offset += 4 - (offset % 4)
        try:
            desc, offset = _read_aligned_string(data, offset)
        except ValueError:
            continue
        if offset + 4 > len(data):
            continue
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if count != language_count:
            continue
        values: List[str] = []
        spans: List[tuple[int, int]] = []
        lengths: List[int] = []
        try:
            for _ in range(count):
                value, start_pos, end_pos, length, offset = _read_aligned_string_with_span(
                    data, offset
                )
                values.append(value)
                spans.append((start_pos, end_pos))
                lengths.append(length)
        except ValueError:
            continue
        entries.append(
            LocalizationEntry(
                key=key,
                offset=start,
                desc=desc,
                values=values,
                spans=spans,
                lengths=lengths,
            )
        )
    return entries


def _load_key_updates(map_path: pathlib.Path) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read key map file: {map_path}") from exc

    if isinstance(payload, dict) and "keys" in payload:
        payload = payload["keys"]

    if not isinstance(payload, dict):
        raise ValueError("Key map JSON must be an object.")

    updates: dict[str, dict[str, str]] = {}
    for key, lang_map in payload.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Key map entries must use non-empty string keys.")
        if not isinstance(lang_map, dict):
            raise ValueError(f"Key map for '{key}' must be an object.")
        normalized: dict[str, str] = {}
        for lang, value in lang_map.items():
            if lang not in DEFAULT_LANGUAGE_ORDER:
                raise ValueError(f"Unknown language code '{lang}' for key '{key}'.")
            if not isinstance(value, str):
                raise ValueError(f"Value for '{key}'/'{lang}' must be a string.")
            normalized[lang] = value
        if not normalized:
            raise ValueError(f"Key map for '{key}' is empty.")
        updates[key] = normalized
    return updates


def _apply_key_updates(
    assets_path: pathlib.Path,
    updates: dict[str, dict[str, str]],
    dry_run: bool,
) -> int:
    data = assets_path.read_bytes()
    patched = bytearray(data)
    code_to_index = {code: idx for idx, code in enumerate(DEFAULT_LANGUAGE_ORDER)}
    changed = False

    for key, lang_map in updates.items():
        entries = _find_key_entries_with_spans(data, key, len(DEFAULT_LANGUAGE_ORDER))
        if not entries:
            print(f"ERROR: Key not found: {key}")
            return 3
        if len(entries) != 1:
            print(f"ERROR: Multiple entries found for key: {key}")
            return 4

        entry = entries[0]
        print(f"Key: {entry.key} (offset={entry.offset})")
        for lang, new_value in lang_map.items():
            idx = code_to_index[lang]
            start_pos, end_pos = entry.spans[idx]
            length = entry.lengths[idx]
            old_value = entry.values[idx]
            new_bytes = new_value.encode("utf-8")
            if len(new_bytes) > length:
                print(
                    f"ERROR: '{entry.key}'/{lang} replacement is longer than "
                    f"existing length ({len(new_bytes)} > {length})."
                )
                return 3
            if old_value == new_value:
                continue
            print(f"{lang}: '{old_value}' -> '{new_value}'")
            if not dry_run:
                patched[start_pos:end_pos] = _pad_bytes(new_bytes, length)
            changed = True

    if not changed:
        print("No changes needed.")
        return 0

    if dry_run:
        print("Dry run OK: key updates would be applied.")
        return 0

    backup_path = _unique_backup_path(assets_path)
    backup_path.write_bytes(data)
    assets_path.write_bytes(bytes(patched))
    print("Key updates applied.")
    print(f"Backup: {backup_path}")
    return 0


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply key-based localization overrides in WaterPark Simulator."
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
        "--key-map",
        default=DEFAULT_KEY_MAP,
        help="JSON key map file (default: key_map.json).",
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

    if args.list:
        libraries = _discover_library_paths()
        game_dirs = _find_game_dirs(libraries)
        if not game_dirs:
            print("No game directories found.")
            return 1
        for path in game_dirs:
            print(path)
        return 0

    assets_path: Optional[pathlib.Path] = None
    if args.assets_path:
        assets_path = pathlib.Path(args.assets_path).expanduser().resolve()
    elif args.game_dir:
        game_dir = pathlib.Path(args.game_dir).expanduser().resolve()
        assets_path = _resolve_assets_path(game_dir)
    else:
        libraries = _discover_library_paths()
        game_dirs = _find_game_dirs(libraries)
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

    key_map_path = pathlib.Path(args.key_map).expanduser().resolve()
    if not key_map_path.exists():
        print(f"ERROR: Key map file not found: {key_map_path}")
        return 2

    try:
        updates = _load_key_updates(key_map_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    return _apply_key_updates(assets_path, updates, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
