"""Entry point: python -m src --help."""

import sys

from .config import config
from .repository import local_graph, normalize, remote_source
from .graph import walk


def report(options):
    """Dispatch a single selected stage without running unrelated stages."""
    if options.mode == "show-config":
        for key, value in vars(options).items():
            print(f"{key}={value}")
        return
    root = options.package
    if options.test_mode:
        graph = local_graph(options.repo)
        if root not in graph:
            raise ValueError(f"Нет пакета {root}")
        lookup = graph.__getitem__
    else:
        root = normalize(root)
        lookup = remote_source(options.repo)
    if options.mode == "direct-only":
        graph = walk(root, lookup, 1, options.filter)
        print("\n".join(sorted(graph.get(root, ()))))
        return
    graph = walk(root, lookup, options.max_depth, options.filter)
    for name, children in graph.items():
        print(name, "->", ", ".join(sorted(children)))


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
