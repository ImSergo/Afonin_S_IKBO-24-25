"""Entry point: python -m src --help."""

import sys

from .config import config


def report(options):
    """Dispatch a single selected stage without running unrelated stages."""
    if options.mode == "show-config":
        for key, value in vars(options).items():
            print(f"{key}={value}")
        return


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
