"""Обход графа зависимостей и его визуализация."""

import json
import os
import shutil
import subprocess
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RENDER_TIMEOUT = 60


def visible(name, blocked):
    """An empty filter never excludes a name."""
    return not blocked or blocked not in name.casefold()


def walk(root, dependencies, limit, excluded=""):
    """Expand again if a shorter path restores remaining depth."""
    blocked = excluded.casefold()
    if not visible(root, blocked):
        return {}
    graph = {}
    best = {}
    stack = [(root, 0)]
    while stack:
        name, depth = stack.pop()
        if name in best and best[name] <= depth:
            continue
        best[name] = depth
        graph.setdefault(name, set())
        if depth >= limit:
            continue
        children = sorted(child for child in dependencies(name)
                          if visible(child, blocked))
        graph[name].update(children)
        stack.extend((child, depth + 1) for child in reversed(children))
    return graph


def reverse_names(root, graph, limit, excluded):
    """Развернуть рёбра и найти потребителей тем же обходом."""
    parents = {name: set() for name in graph}
    for name, children in graph.items():
        for child in children:
            parents.setdefault(child, set()).add(name)
    parents.setdefault(root, set())
    found = walk(root, parents.__getitem__, limit, excluded)
    return sorted(set(found) - {root})


def dot_text(graph):
    """Quote names, retain isolated nodes and sort edges for clean diffs."""
    lines = ["digraph dependencies {", "  rankdir=LR;"]
    for name in sorted(graph):
        source = json.dumps(name)
        lines.append(f"  {source};")
        for child in sorted(graph[name]):
            lines.append(f"  {source} -> {json.dumps(child)};")
    return "\n".join([*lines, "}", ""])


def renderer_path():
    """Find dot on PATH or in a per-user Windows Graphviz installation."""
    override = os.environ.get("GRAPHVIZ_DOT") or shutil.which("dot")
    if override:
        return override
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        programs = Path(os.environ["LOCALAPPDATA"]) / "Programs"
        for path in sorted(programs.glob("Graphviz*/bin/dot.exe")):
            return str(path)
    return "dot"


def render(text, output):
    """Only write results after Graphviz returns a PNG successfully."""
    command = [renderer_path(), "-Tpng"]
    try:
        result = subprocess.run(command, input=text.encode(),
                                capture_output=True, timeout=RENDER_TIMEOUT)
    except FileNotFoundError as error:
        raise ValueError("Не найден Graphviz dot: укажите GRAPHVIZ_DOT") \
            from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("Истекло время ожидания Graphviz") from error
    if result.returncode or not result.stdout.startswith(PNG_SIGNATURE):
        detail = result.stderr.decode(errors="replace").strip()
        raise ValueError(f"Graphviz не создал PNG: {detail}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".dot").write_text(text, encoding="utf-8")
    output.write_bytes(result.stdout)
