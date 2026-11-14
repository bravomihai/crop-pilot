"""Access to the shared contracts (schemas + examples) in /contracts."""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACTS_DIR = Path(os.environ.get("FIELDSHIFT_CONTRACTS", Path(__file__).resolve().parents[2] / "contracts"))

# Plain dicts are the interchange format; these aliases document intent.
FarmRequest = dict[str, Any]
FieldData = dict[str, Any]
CropRules = dict[str, Any]
Evaluation = dict[str, Any]
AnalysisResult = dict[str, Any]


def example(name: str) -> dict[str, Any]:
    """Load contracts/examples/<name>.example.json, e.g. example("field-data")."""
    path = CONTRACTS_DIR / "examples" / f"{name}.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def _registry() -> Registry:
    resources = []
    for p in (CONTRACTS_DIR / "schemas").glob("*.schema.json"):
        schema = json.loads(p.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@lru_cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=_registry())


def validate(name: str, data: dict[str, Any]) -> list[str]:
    """Return a list of human-readable errors (empty list = valid)."""
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in _validator(name).iter_errors(data)
    ]
