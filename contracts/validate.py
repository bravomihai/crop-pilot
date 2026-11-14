"""Validate every example in contracts/examples against its schema.

Usage:  python contracts/validate.py [file.json ...]
With no arguments, validates all examples. With arguments, each file is
matched to a schema by its name prefix (e.g. my-farm-request.json → farm-request).
Requires: pip install jsonschema
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).parent
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"
NAMES = ["farm-request", "field-data", "crop-rules", "evaluation", "analysis-result"]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def registry() -> Registry:
    resources = []
    for p in SCHEMAS.glob("*.schema.json"):
        schema = load(p)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def schema_name_for(path: Path) -> str:
    for name in sorted(NAMES, key=len, reverse=True):
        if name in path.name:
            return name
    raise SystemExit(f"Cannot tell which schema applies to {path.name}")


def validate(path: Path, reg: Registry) -> list[str]:
    name = schema_name_for(path)
    schema = load(SCHEMAS / f"{name}.schema.json")
    validator = Draft202012Validator(schema, registry=reg, format_checker=FormatChecker())
    return [
        f"{path.name}: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(load(path))
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    reg = registry()
    files = [Path(a) for a in sys.argv[1:]] or sorted(EXAMPLES.glob("*.json"))
    errors = [err for f in files for err in validate(f, reg)]
    for err in errors:
        print("FAIL", err)
    print(f"{len(files)} file(s) checked, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
