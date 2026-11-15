"""The installed engine (Docker uses a non-editable install) must ship every data file."""

from __future__ import annotations

import tomllib
from fnmatch import fnmatch
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
DATA_SUFFIXES = {".json", ".geojson"}


def test_every_runtime_data_file_is_declared_as_package_data():
    config = tomllib.loads((ENGINE / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]
    missing = []
    for path in sorted((ENGINE / "fieldshift").rglob("*")):
        if path.suffix not in DATA_SUFFIXES or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(ENGINE).as_posix()
        covered = False
        for package, patterns in package_data.items():
            prefix = package.replace(".", "/") + "/"
            if relative.startswith(prefix):
                inside = relative[len(prefix):]
                covered = covered or any(fnmatch(inside, pattern) and inside.count("/") == pattern.count("/") for pattern in patterns)
        if not covered:
            missing.append(relative)
    assert not missing, f"not packaged (absent from the Docker image): {missing}"
