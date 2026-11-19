"""Read an adjacency list or PyPI JSON without a package manager."""

import json
import re
from functools import cache
from http.client import HTTPException
from pathlib import Path
from urllib.request import urlopen

from .config import PACKAGE, TEST_NAME


TIMEOUT = 15
REQUIREMENT = re.compile(rf"^\s*({PACKAGE})(?=\s|[\[(@<>=!~;]|$)")


def normalize(name):
    """Canonicalize a Python distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def names_from_metadata(data):
    """Read all declared names, including conditional requirements."""
    if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
        raise ValueError("В ответе PyPI отсутствует объект info")
    requirements = data["info"].get("requires_dist")
    if requirements is None:
        return ()
    if not isinstance(requirements, list):
        raise ValueError("requires_dist должен быть списком")
    names = set()
    for entry in requirements:
        match = REQUIREMENT.match(entry) if isinstance(entry, str) else None
        if not match:
            raise ValueError(f"Некорректная запись Requires-Dist: {entry!r}")
        names.add(normalize(match.group(1)))
    return tuple(sorted(names))


def remote_source(base):
    """Build a cached lookup for the configured PyPI-compatible registry."""
    prefix = base.rstrip("/")
    if not prefix.endswith("/pypi"):
        prefix += "/pypi"

    @cache
    def dependencies(name):
        """Read the project's latest release, with package-specific errors."""
        try:
            with urlopen(f"{prefix}/{name}/json", timeout=TIMEOUT) as reply:
                return names_from_metadata(json.load(reply))
        except (OSError, HTTPException, ValueError) as error:
            raise ValueError(f"Не удалось прочитать пакет {name}: {error}")

    return dependencies


def local_graph(filename):
    """Validate the entire fixture and add any implicit leaf nodes."""
    data = json.loads(Path(filename).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Тестовый репозиторий должен быть объектом JSON")
    graph = {}
    for name, children in data.items():
        if not re.fullmatch(TEST_NAME, name) or not isinstance(children, list):
            raise ValueError(f"Некорректная запись пакета {name!r}")
        for child in children:
            if not isinstance(child, str) or not re.fullmatch(TEST_NAME, child):
                raise ValueError(f"Некорректная зависимость {child!r}")
            graph.setdefault(child, ())
        graph[name] = tuple(sorted(set(children)))
    return graph
