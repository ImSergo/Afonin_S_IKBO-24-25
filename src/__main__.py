"""Entry point: python -m src --help."""

import sys

from .config import config
from .graph import dot_text, render, reverse_names, walk
from .repository import local_graph, normalize, remote_source


def source_for(options):
    """Return a package name, lookup and optional finite reverse index."""
    if options.test_mode:
        graph = local_graph(options.repo)
        if options.package not in graph:
            raise ValueError(f"Пакет {options.package} отсутствует в файле")
        return options.package, graph.__getitem__, graph
    lookup = remote_source(options.repo)
    graph = {}
    for root in options.scope:
        part = walk(normalize(root), lookup, options.max_depth, options.filter)
        for name, children in part.items():
            graph.setdefault(name, set()).update(children)
    return normalize(options.package), lookup, graph


def report(options):
    """Dispatch a single selected stage without running unrelated stages."""
    if options.mode == "show-config":
        for key, value in vars(options).items():
            print(f"{key}={value}")
        return
    root, lookup, index = source_for(options)
    if options.mode == "reverse":
        names = reverse_names(root, index, options.max_depth, options.filter)
        print("\n".join(names))
        return
    if options.mode == "direct-only":
        graph = walk(root, lookup, 1, options.filter)
        print("\n".join(sorted(graph.get(root, ()))))
        return
    graph = walk(root, lookup, options.max_depth, options.filter)
    text = dot_text(graph)
    if options.mode != "graph-only":
        render(text, options.output)
    print(text, end="")


def main(arguments=None):
    """Use exit code 1 for data/render failures, 2 for invalid options."""
    options = config(arguments)
    try:
        report(options)
    except (ValueError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
