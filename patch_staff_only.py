#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import mmap
import os
import pathlib
import re
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

GAME_DIR_NAME = "WaterPark Simulator"
DATA_SUBDIR = "WaterparkSimulator_Data"
ASSETS_FILE = "resources.assets"

OLD_TEXT = "ТОЛЬКО ПЕРСОНАЛ"
DEFAULT_NEW_TEXT = "STAFF ONLY"
LANGUAGE_LIST_MARKER = b"\x07\x00\x00\x00English"
SEARCH_WINDOW_BYTES = 8 * 1024 * 1024
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
class Replacement:
    old: str
    new: str
    label: str


@dataclass(frozen=True)
class LanguageEntry:
    name: str
    code: str
    raw: bytes


@dataclass(frozen=True)
class LanguageSource:
    index: int
    start: int
    end: int
    entries: List[LanguageEntry]
    codes: List[str]


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

def _load_search_data(assets_path: pathlib.Path) -> tuple[bytes, int]:
    with assets_path.open("rb") as handle:
        mapping = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        marker_index = mapping.find(LANGUAGE_LIST_MARKER)
        if marker_index == -1:
            mapping.close()
            raise ValueError("Language list marker not found in assets.")
        start = max(0, marker_index - SEARCH_WINDOW_BYTES)
        end = min(len(mapping), marker_index + SEARCH_WINDOW_BYTES)
        data = mapping[start:end]
        mapping.close()
    return data, start


def _looks_like_key(text: str, require_slash: bool) -> bool:
    if not text or len(text) > 160:
        return False
    if require_slash and "/" not in text:
        return False
    for ch in text:
        if ch.isalnum() or ch in "/._-":
            continue
        return False
    return True


def _find_all_markers(data: bytes, marker: bytes) -> List[int]:
    positions: List[int] = []
    start = 0
    while True:
        index = data.find(marker, start)
        if index == -1:
            break
        positions.append(index)
        start = index + 1
    return positions


def _parse_language_entries_at(
    data: bytes, start: int, count: int
) -> tuple[int, List[LanguageEntry]]:
    offset = start
    entries: List[LanguageEntry] = []
    for _ in range(count):
        entry_start = offset
        name, offset = _read_aligned_string(data, offset)
        code, offset = _read_aligned_string(data, offset)
        if offset + 4 > len(data):
            raise ValueError("Unexpected end of data while reading language entry.")
        offset += 4
        entries.append(LanguageEntry(name=name, code=code, raw=data[entry_start:offset]))
    return offset, entries


def _collect_language_sources(data: bytes, count: int) -> List[LanguageSource]:
    sources: List[LanguageSource] = []
    for start in _find_all_markers(data, LANGUAGE_LIST_MARKER):
        try:
            end, entries = _parse_language_entries_at(data, start, count)
        except ValueError:
            continue
        codes = [entry.code for entry in entries]
        sources.append(
            LanguageSource(
                index=len(sources),
                start=start,
                end=end,
                entries=entries,
                codes=codes,
            )
        )
    return sources


def _list_language_sources(data: bytes, desired_codes: Sequence[str]) -> int:
    sources = _collect_language_sources(data, len(desired_codes))
    if not sources:
        print("No language sources found.")
        return 1
    desired_set = set(desired_codes)
    desired_list = list(desired_codes)
    for source in sources:
        if set(source.codes) == desired_set:
            status = "ok" if source.codes == desired_list else "reorder"
        else:
            status = "mismatch"
        print(
            f"[{source.index}] offset={source.start} codes="
            f"{','.join(source.codes)} ({status})"
        )
    return 0


def _select_language_sources(
    data: bytes,
    desired_codes: Sequence[str],
    source_index: Optional[int],
    fix_all: bool,
) -> List[LanguageSource]:
    sources = _collect_language_sources(data, len(desired_codes))
    if not sources:
        raise ValueError("No language sources found.")
    desired_set = set(desired_codes)
    matching = [source for source in sources if set(source.codes) == desired_set]

    if source_index is not None:
        if source_index < 0 or source_index >= len(sources):
            raise ValueError(
                "Language source index out of range. Use --list-language-sources."
            )
        selected = sources[source_index]
        if set(selected.codes) != desired_set:
            raise ValueError("Selected language source does not match desired codes.")
        return [selected]

    if fix_all:
        if not matching:
            raise ValueError("No language sources match the desired codes.")
        return matching

    if len(matching) == 1:
        return matching

    if not matching:
        raise ValueError("No language sources match the desired codes.")

    raise ValueError(
        "Multiple language sources found. Use --list-language-sources and "
        "--language-source-index."
    )


def _iter_localization_entries(
    data: bytes, language_count: int, require_slash: bool
) -> Iterable[tuple[str, str, List[str], int]]:
    offset = 0
    data_len = len(data)
    step = 4
    seen = set()

    while offset + 4 <= data_len:
        length = struct.unpack_from("<I", data, offset)[0]
        if 1 <= length <= 160:
            key_start = offset + 4
            key_end = key_start + length
            if key_end <= data_len:
                key_bytes = data[key_start:key_end]
                try:
                    key = key_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    key = ""
                if key and _looks_like_key(key, require_slash):
                    try:
                        pos = key_end
                        if pos % 4:
                            pos += 4 - (pos % 4)
                        desc, pos = _read_aligned_string(data, pos)
                        if pos + 4 > data_len:
                            raise ValueError
                        count = struct.unpack_from("<I", data, pos)[0]
                        pos += 4
                        if count != language_count:
                            raise ValueError
                        values: List[str] = []
                        for _ in range(count):
                            value, pos = _read_aligned_string(data, pos)
                            values.append(value)
                    except ValueError:
                        pass
                    else:
                        if key not in seen:
                            seen.add(key)
                            yield key, desc, values, offset
                        offset = pos
                        continue
        offset += step


def _search_localization(
    assets_path: pathlib.Path,
    text_query: Optional[str],
    key_query: Optional[str],
    ignore_case: bool,
    require_slash: bool,
    source_index: Optional[int],
) -> int:
    try:
        data, base_offset = _load_search_data(assets_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    if not text_query and not key_query:
        print("ERROR: Provide --search-text or --search-key.")
        return 2

    codes: Optional[List[str]] = None
    sources = _collect_language_sources(data, len(DEFAULT_LANGUAGE_ORDER))
    if sources:
        if source_index is not None:
            if source_index < 0 or source_index >= len(sources):
                print("ERROR: Language source index out of range.")
                return 2
            codes = sources[source_index].codes
        elif len(sources) == 1:
            codes = sources[0].codes

    if ignore_case:
        text_query_cmp = text_query.casefold() if text_query else None
        key_query_cmp = key_query.casefold() if key_query else None
    else:
        text_query_cmp = text_query
        key_query_cmp = key_query

    matches = 0
    for key, desc, values, entry_start in _iter_localization_entries(
        data, len(DEFAULT_LANGUAGE_ORDER), require_slash
    ):
        key_cmp = key.casefold() if ignore_case else key
        if key_query_cmp and key_query_cmp not in key_cmp:
            continue

        hits: List[tuple[str, str]] = []
        if text_query_cmp:
            for idx, value in enumerate(values):
                value_cmp = value.casefold() if ignore_case else value
                if text_query_cmp in value_cmp:
                    label = str(idx + 1)
                    if codes and idx < len(codes):
                        label = codes[idx]
                    hits.append((label, value))

        if text_query_cmp and not hits:
            continue

        matches += 1
        print(f"Key: {key} (offset={entry_start + base_offset})")
        if desc:
            print(f"Desc: {desc}")
        if hits:
            for label, value in hits:
                print(f"{label}: {value}")
        elif not text_query_cmp:
            print("Match.")

    if matches == 0:
        print("No matches found.")
        return 1
    return 0


def _parse_language_order(order_text: Optional[str]) -> List[str]:
    if not order_text:
        return list(DEFAULT_LANGUAGE_ORDER)
    codes = [code.strip() for code in order_text.split(",") if code.strip()]
    if len(codes) != len(DEFAULT_LANGUAGE_ORDER):
        raise ValueError(
            "Language order must include "
            f"{len(DEFAULT_LANGUAGE_ORDER)} codes: {','.join(DEFAULT_LANGUAGE_ORDER)}"
        )
    if len(set(codes)) != len(codes):
        raise ValueError("Language order contains duplicates.")
    if set(codes) != set(DEFAULT_LANGUAGE_ORDER):
        raise ValueError(
            "Language order must use the same codes: "
            f"{','.join(DEFAULT_LANGUAGE_ORDER)}"
        )
    return codes


def _reorder_language_list(
    data: bytes,
    desired_codes: Sequence[str],
    dry_run: bool,
    source_index: Optional[int],
    fix_all: bool,
) -> tuple[bytes, List[LanguageSource], List[LanguageSource]]:
    selected_sources = _select_language_sources(
        data, desired_codes, source_index, fix_all
    )
    desired_list = list(desired_codes)
    patched = bytearray(data)
    changed_sources: List[LanguageSource] = []

    for source in selected_sources:
        current_codes = source.codes
        if current_codes == desired_list:
            continue
        entry_by_code = {entry.code: entry for entry in source.entries}
        new_block = b"".join(entry_by_code[code].raw for code in desired_list)
        if len(new_block) != (source.end - source.start):
            raise ValueError("Language list size mismatch; aborting.")
        if not dry_run:
            patched[source.start : source.end] = new_block
        changed_sources.append(source)

    return bytes(patched), selected_sources, changed_sources


def _fix_language_order(
    assets_path: pathlib.Path,
    desired_codes: Sequence[str],
    dry_run: bool,
    source_index: Optional[int],
    fix_all: bool,
) -> int:
    data = assets_path.read_bytes()
    try:
        patched, selected_sources, changed_sources = _reorder_language_list(
            data, desired_codes, dry_run, source_index, fix_all
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 3

    desired_list = list(desired_codes)
    for source in selected_sources:
        print(f"[{source.index}] Current order: " + ",".join(source.codes))
    print("Desired order: " + ",".join(desired_list))

    if not changed_sources:
        print("Language order already correct for selected sources.")
        return 0

    if dry_run:
        print("Dry run OK: language order would be updated.")
        return 0

    backup_path = _unique_backup_path(assets_path)
    backup_path.write_bytes(data)
    assets_path.write_bytes(patched)
    print("Language order updated.")
    print(f"Backup: {backup_path}")
    return 0


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


def _load_replacements(map_path: pathlib.Path) -> List[Replacement]:
    try:
        payload = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read mapping file: {map_path}") from exc

    if isinstance(payload, dict):
        if "replacements" in payload:
            items = payload["replacements"]
        else:
            items = [{"old": k, "new": v} for k, v in payload.items()]
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Mapping JSON must be an object or array.")

    replacements: List[Replacement] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Replacement entry #{idx} must be an object.")
        old = item.get("old")
        new = item.get("new")
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError(f"Replacement entry #{idx} must include string 'old' and 'new'.")
        label = item.get("label") if isinstance(item.get("label"), str) else old
        replacements.append(Replacement(old=old, new=new, label=label))
    return replacements


def _build_replacements(map_file: Optional[str], new_text: str) -> List[Replacement]:
    if map_file:
        map_path = pathlib.Path(map_file).expanduser().resolve()
        if not map_path.exists():
            raise ValueError(f"Mapping file not found: {map_path}")
        replacements = _load_replacements(map_path)
        if not replacements:
            raise ValueError(f"No replacements found in mapping file: {map_path}")
        return replacements
    return [Replacement(old=OLD_TEXT, new=new_text, label="default")]


def _find_localization_entries(
    data: bytes, key: str
) -> List[tuple[int, str, List[str]]]:
    key_bytes = key.encode("utf-8")
    needle = struct.pack("<I", len(key_bytes)) + key_bytes
    offsets = _find_occurrences(data, needle)
    entries: List[tuple[int, str, List[str]]] = []

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
        if count <= 0 or count > 100:
            continue
        values: List[str] = []
        try:
            for _ in range(count):
                value, offset = _read_aligned_string(data, offset)
                values.append(value)
        except ValueError:
            continue
        entries.append((start, desc, values))
    return entries


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
    allow_multiple: bool,
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
        if len(entries) != 1 and not allow_multiple:
            print(f"ERROR: Multiple entries found for key: {key}")
            return 4

        for entry in entries:
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
def _dump_key(
    assets_path: pathlib.Path, key: str, source_index: Optional[int]
) -> int:
    data = assets_path.read_bytes()
    entries = _find_localization_entries(data, key)
    if not entries:
        print(f"Key not found: {key}")
        return 2

    codes: Optional[List[str]] = None
    sources = _collect_language_sources(data, len(DEFAULT_LANGUAGE_ORDER))
    if sources:
        if source_index is not None:
            if source_index < 0 or source_index >= len(sources):
                print("ERROR: Language source index out of range.")
                return 2
            codes = sources[source_index].codes
        elif len(sources) == 1:
            codes = sources[0].codes
        else:
            print("Multiple language sources found. Use --language-source-index to label.")

    for entry_start, desc, values in entries:
        print(f"Key: {key} (offset={entry_start})")
        if desc:
            print(f"Desc: {desc}")
        for idx, value in enumerate(values, start=1):
            label = str(idx)
            if codes and idx - 1 < len(codes):
                label = codes[idx - 1]
            print(f"{label}: {value}")
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


def _patch_assets(
    assets_path: pathlib.Path,
    replacements: Sequence[Replacement],
    dry_run: bool,
    allow_multiple: bool,
) -> int:
    data = assets_path.read_bytes()

    planned: List[tuple[bytes, bytes, List[int], str]] = []
    already_patched: List[str] = []
    missing: List[str] = []
    seen_old: set[bytes] = set()

    for replacement in replacements:
        old_bytes = replacement.old.encode("utf-8")
        if old_bytes in seen_old:
            print(f"ERROR: Duplicate old string in replacements: {replacement.label}")
            return 4
        seen_old.add(old_bytes)

        new_bytes = replacement.new.encode("utf-8")
        try:
            new_padded = _pad_bytes(new_bytes, len(old_bytes))
        except ValueError:
            print(f"ERROR: Replacement '{replacement.label}' is longer than original.")
            return 3

        positions = _find_occurrences(data, old_bytes)
        if not positions:
            if new_padded in data:
                already_patched.append(replacement.label)
                continue
            missing.append(replacement.label)
            continue
        if not allow_multiple and len(positions) != 1:
            print(
                f"ERROR: Unexpected occurrence count for '{replacement.label}': {len(positions)}"
            )
            return 4
        planned.append((old_bytes, new_padded, positions, replacement.label))

    if missing:
        print("ERROR: Target string(s) not found:")
        for label in missing:
            print(f" - {label}")
        return 3
    if not planned:
        print("Already patched.")
        return 0

    if dry_run:
        for _, _, positions, label in planned:
            print(f"Will patch '{label}' ({len(positions)} occurrence(s)).")
        if already_patched:
            for label in already_patched:
                print(f"Already patched: {label}")
        print("Dry run OK: patch would be applied.")
        return 0

    backup_path = _unique_backup_path(assets_path)
    backup_path.write_bytes(data)

    patched = bytearray(data)
    for old_bytes, new_padded, positions, _ in planned:
        for pos in positions:
            patched[pos : pos + len(old_bytes)] = new_padded
    patched_bytes = bytes(patched)
    assets_path.write_bytes(patched_bytes)

    if len(patched_bytes) != len(data):
        print("WARNING: File size changed unexpectedly.")

    print("Patched successfully.")
    print(f"Backup: {backup_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch localized strings in WaterPark Simulator."
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
        help="Replacement text (UTF-8). Default: STAFF ONLY. Ignored with --map-file.",
    )
    parser.add_argument(
        "--map-file",
        default=None,
        help="JSON mapping file with multiple replacements (overrides --text).",
    )
    parser.add_argument(
        "--key-map",
        default=None,
        help="JSON key map file for per-key language overrides.",
    )
    parser.add_argument(
        "--fix-language-order",
        action="store_true",
        help="Fix language order so UI selection maps to the correct columns.",
    )
    parser.add_argument(
        "--language-order",
        default=None,
        help="Comma-separated language codes for --fix-language-order.",
    )
    parser.add_argument(
        "--list-language-sources",
        action="store_true",
        help="List language sources in the localization table and exit.",
    )
    parser.add_argument(
        "--language-source-index",
        type=int,
        default=None,
        help="Language source index from --list-language-sources.",
    )
    parser.add_argument(
        "--fix-all-language-sources",
        action="store_true",
        help="Apply language order fix to all matching language sources.",
    )
    parser.add_argument(
        "--dump-key",
        default=None,
        help="Dump translations for a localization key and exit.",
    )
    parser.add_argument(
        "--search-text",
        default=None,
        help="Search localization entries for this text in translations.",
    )
    parser.add_argument(
        "--search-key",
        default=None,
        help="Search localization keys for this substring.",
    )
    parser.add_argument(
        "--search-ignore-case",
        action="store_true",
        help="Case-insensitive search for --search-text/--search-key.",
    )
    parser.add_argument(
        "--search-all-keys",
        action="store_true",
        help="Include keys without '/' when searching.",
    )
    parser.add_argument(
        "--allow-multiple",
        action="store_true",
        help="Allow a replacement when the target string appears multiple times.",
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

    if args.list_language_sources:
        try:
            desired_codes = _parse_language_order(args.language_order)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
        return _list_language_sources(assets_path.read_bytes(), desired_codes)

    if args.dump_key:
        return _dump_key(assets_path, args.dump_key, args.language_source_index)

    if args.search_text or args.search_key:
        return _search_localization(
            assets_path,
            args.search_text,
            args.search_key,
            args.search_ignore_case,
            not args.search_all_keys,
            args.language_source_index,
        )

    if args.key_map:
        try:
            updates = _load_key_updates(pathlib.Path(args.key_map).expanduser().resolve())
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
        return _apply_key_updates(assets_path, updates, args.dry_run, args.allow_multiple)

    if args.fix_language_order:
        try:
            desired_codes = _parse_language_order(args.language_order)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
        return _fix_language_order(
            assets_path,
            desired_codes,
            args.dry_run,
            args.language_source_index,
            args.fix_all_language_sources,
        )

    try:
        replacements = _build_replacements(args.map_file, args.text)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    return _patch_assets(assets_path, replacements, args.dry_run, args.allow_multiple)


if __name__ == "__main__":
    sys.exit(main())
