"""Candidate generation: every ordered sequence of three main crops from P3's rule set.

P4 does not decide which successions are agronomically acceptable (same crop twice,
previous-crop conflicts, autumn sowing...). It enumerates the search space, removes the
farmer's exclusions and lets P3's evaluator accept or reject each sequence.
"""

from __future__ import annotations

import hashlib
import heapq
import itertools
import re
from dataclasses import dataclass

from .config import SEQUENCE_LENGTH

_CROP_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class CropInfo:
    crop_id: str
    name: str | None


@dataclass(frozen=True)
class CandidateSet:
    candidates: tuple[tuple[str, ...], ...]
    crops: tuple[str, ...]
    total_space: int
    truncated: bool


def crop_catalog(rules: dict) -> tuple[dict[str, CropInfo], list[str]]:
    """Read supported crops from `rules["crops"]` (dict id→info or list of objects).

    Returns the catalog and human-readable issues. Unparseable entries are skipped,
    never guessed. The `crops` key is part of the proposed P3 rules shape.
    """
    issues: list[str] = []
    raw = rules.get("crops") if isinstance(rules, dict) else None
    entries: list[tuple[object, object]] = []
    if isinstance(raw, dict):
        entries = list(raw.items())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                entries.append((item.get("id", item.get("crop_id")), item))
            else:
                entries.append((item, {}))
    elif raw is not None:
        issues.append("The regional rules contain an unrecognized `crops` field.")
    catalog: dict[str, CropInfo] = {}
    for crop_id, info in entries:
        if not isinstance(crop_id, str) or not _CROP_ID.match(crop_id):
            issues.append(f"Ignored invalid crop identifier: {crop_id!r}.")
            continue
        name = None
        if isinstance(info, dict):
            for key in ("name", "display_name", "crop_name"):
                if isinstance(info.get(key), str) and info[key].strip():
                    name = info[key].strip()
                    break
        if crop_id not in catalog:  # duplicate entries collapse to the first one
            catalog[crop_id] = CropInfo(crop_id, name)
    return catalog, issues


def _sample_key(sequence: tuple[str, ...]) -> str:
    return hashlib.sha256(">".join(sequence).encode()).hexdigest()


def generate_candidates(
    crop_ids, excluded=(), max_candidates: int = 1500, length: int = SEQUENCE_LENGTH
) -> CandidateSet:
    """Enumerate ordered sequences with replacement, deterministically.

    - Crop IDs are de-duplicated and sorted; excluded crops never appear.
    - If n**length <= max_candidates, all sequences are returned in lexicographic order.
    - Otherwise a deterministic, order-independent sample of `max_candidates` sequences
      is chosen by smallest SHA-256 digest (unbiased with respect to crop names), then
      returned in lexicographic order. `truncated=True` must be reported to the user.
    """
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    crops = tuple(sorted(set(crop_ids) - set(excluded)))
    total = len(crops) ** length if crops else 0
    if total == 0:
        return CandidateSet((), crops, 0, False)
    space = itertools.product(crops, repeat=length)
    if total <= max_candidates:
        return CandidateSet(tuple(space), crops, total, False)
    sample = heapq.nsmallest(max_candidates, space, key=_sample_key)
    return CandidateSet(tuple(sorted(sample)), crops, total, True)


def signature(sequence) -> str:
    return ">".join(sequence)
