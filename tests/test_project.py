"""Проверки текущего этапа."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from src.__main__ import main


def invoke(arguments):
    """Capture the same streams and exit status as a console process."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            status = main(arguments)
        except SystemExit as error:
            status = error.code
    return status, stdout.getvalue(), stderr.getvalue()


class CommandTests(unittest.TestCase):
    """Проверить параметры и сообщения об ошибках."""

    def test_config(self):
        status, output, _ = invoke(["-p", "demo", "--show-config"])
        self.assertEqual(status, 0)
        self.assertIn("package=demo", output)

    def test_invalid_depth(self):
        self.assertEqual(invoke(["-p", "demo", "-d", "-1"])[0], 2)
