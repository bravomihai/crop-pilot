"""P3 owns regional rules and evaluation, independent of farmer priority weights.

Implement compatibility, previous-crop checks, crop-specific exposure and calendar windows.
Preserve unknown inputs; do not invent neutral scores or infer field soil from coarse moisture.
Every numeric estimate must identify its source and calculation.
"""


def load_rules(location: dict) -> dict:
    raise NotImplementedError("Regional agronomic rules are not implemented")


def evaluate(
    rotation: list[str], request: dict, environment: dict, rules: dict
) -> dict:
    raise NotImplementedError("Agronomic rotation evaluation is not implemented")
