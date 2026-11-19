"""Обход графа зависимостей."""


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
