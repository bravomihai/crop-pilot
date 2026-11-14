"""P3: regional rules and the evaluation of one rotation, independent of farmer priorities.

`load_rules(location)` returns the regional knowledge (crops, calendars, FAO-56 and EcoCrop
parameters, successions, sources). `evaluate(rotation, request, environment, rules)` places
the rotation in time, checks it against the rules, replays it over every past season in the
environment (with the hypothetical scenario applied) and returns four criterion scores in
[0, 1] with their evidence. Unknown inputs give `None` scores, never a neutral value.
"""

from __future__ import annotations

from .core import evaluate
from .rules import load_rules

__all__ = ["evaluate", "load_rules"]
