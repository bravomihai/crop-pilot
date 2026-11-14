"""P4 owns generation, constraints, comparison and explanations.

Generate THREE distinct plans of THREE successive main crops. Apply priorities only here.
Call the P3 evaluator; preserve source references and caveats. Calendar time matters.
Return fewer than three plans with status limited/insufficient_data when necessary.
Never fill missing alternatives with infeasible or duplicate plans.
"""

from typing import Callable


def recommend_rotations(
    request: dict, environment: dict, rules: dict, evaluate: Callable
) -> list[dict]:
    raise NotImplementedError("Rotation generation and selection are not implemented")
