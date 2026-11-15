"""Shared generated JSON schemas, exported from packages/contracts/src/index.ts."""

import json
import os
from functools import lru_cache
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS_DIR = Path(
    os.getenv(
        "CROPPILOT_CONTRACTS",
        Path(__file__).resolve().parents[3] / "packages" / "contracts",
    )
)


@lru_cache
def validator(name: str) -> Draft202012Validator:
    path = CONTRACTS_DIR / "schemas" / f"{name}.schema.json"
    return Draft202012Validator(
        json.loads(path.read_text()), format_checker=FormatChecker()
    )


def validate(name: str, value: dict) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in validator(name).iter_errors(value)
    ]


def example(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / "examples" / f"{name}.json").read_text())
