"""Continue the farmer's `current_rotation` cycle for the next three main crops.

This is sequence bookkeeping, not agronomy: P3 still evaluates the result.

Alignment: the most recent history crops (oldest → newest, see validation.ordered_history)
are matched backwards against the cycle. The cycle position with the longest consecutive
match is taken as "where the farmer is now", and the continuation starts at the next
position. Example: cycle [maize, winter_wheat], last history crop maize → next crops
winter_wheat, maize, winter_wheat.

- No history, or the latest crop is not in the cycle: P4 cannot locate the position. It
  starts from the first listed crop and reports this as an assumption (`aligned=False`).
- Several positions match equally well (for example [maize, maize, wheat] after one
  maize): the earliest position is used and `ambiguous=True` is reported.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import SEQUENCE_LENGTH


@dataclass(frozen=True)
class RotationContinuation:
    cycle: tuple[str, ...]
    sequence: tuple[str, ...]
    aligned: bool
    matched: int  # consecutive history entries matched against the cycle
    ambiguous: bool


def continue_rotation(cycle, history_ordered, length: int = SEQUENCE_LENGTH) -> RotationContinuation:
    cycle = tuple(cycle)
    if not cycle:
        raise ValueError("current_rotation must contain at least one crop")
    n = len(cycle)
    crops = [entry["crop_id"] for entry in history_ordered or []]
    best_matched, best_positions = 0, []
    for k in range(n):  # k = cycle index of the most recent history crop
        matched = 0
        while matched < len(crops) and crops[-1 - matched] == cycle[(k - matched) % n]:
            matched += 1
        if matched > best_matched:
            best_matched, best_positions = matched, [k]
        elif matched == best_matched and matched > 0:
            best_positions.append(k)
    if best_matched == 0:
        start, aligned, ambiguous = 0, False, False
    else:
        start, aligned, ambiguous = (best_positions[0] + 1) % n, True, len(best_positions) > 1
    sequence = tuple(cycle[(start + i) % n] for i in range(length))
    return RotationContinuation(cycle, sequence, aligned, best_matched, ambiguous)
