"""Command-line options shared by all five stages."""

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit


PACKAGE = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
TEST_NAME = r"[A-Z]+"
DEFAULT_DEPTH = 3


def parser():
    """Describe inputs and mutually exclusive reporting modes."""
    cli = argparse.ArgumentParser(description="Граф зависимостей Python")
    cli.add_argument("-p", "--package", required=True)
    cli.add_argument("-r", "--repo", default="https://pypi.org/pypi")
    cli.add_argument("-t", "--test-mode", action="store_true")
    cli.add_argument("-o", "--output", type=Path, default=Path("graph.png"))
    cli.add_argument("-d", "--max-depth", type=int, default=DEFAULT_DEPTH)
    cli.add_argument("-f", "--filter", default="")
    modes = cli.add_mutually_exclusive_group()
    for flag in ("show-config","direct-only","graph-only",):
        modes.add_argument(f"--{flag}", dest="mode", action="store_const",
                           const=flag)
    cli.set_defaults(mode="graph-only")
    return cli


def validate_source(options):
    """Check the repository type before attempting any read."""
    if options.test_mode:
        if not Path(options.repo).is_file():
            raise ValueError("--repo: нужен существующий файл графа")
        return
    parts = urlsplit(options.repo)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("--repo: нужен HTTP(S) URL репозитория")
    if parts.query or parts.fragment or re.search(r"\s", options.repo):
        raise ValueError("--repo: недопустимый URL репозитория")
    if parts.port == 0:
        raise ValueError("--repo: недопустимый порт")


def validate_query(options):
    """Check package names, substring and depth."""
    pattern = TEST_NAME if options.test_mode else PACKAGE
    for name in [options.package]:
        if not re.fullmatch(pattern, name):
            raise ValueError(f"Недопустимое имя пакета: {name!r}")
    if options.max_depth < 0:
        raise ValueError("--max-depth: глубина не может быть меньше нуля")
    if options.filter and not options.filter.strip():
        raise ValueError("--filter: подстрока не может состоять из пробелов")


def validate_outputs(options):
    """Require a PNG destination distinct from the input file."""
    output = options.output
    if output.suffix.lower() != ".png" or output.is_dir():
        raise ValueError("--output: нужен путь к файлу .png")
    targets = (output.resolve(), output.with_suffix(".dot").resolve())
    if options.test_mode and Path(options.repo).resolve() in targets:
        raise ValueError("--output: совпадение с входным файлом")


def config(arguments=None):
    """Parse arguments and reject invalid combinations."""
    cli = parser()
    options = cli.parse_args(arguments)
    try:
        validate_source(options)
        validate_query(options)
        validate_outputs(options)
    except (OSError, ValueError) as error:
        cli.error(str(error))
    return options
