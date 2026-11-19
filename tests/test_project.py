"""Проверки текущего этапа."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from src.__main__ import main
from src.repository import names_from_metadata, remote_source
from src.graph import reverse_names, walk


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


class RepositoryTests(unittest.TestCase):
    """Use the same reader on controlled fixtures and API responses."""

    def test_pep_names_conditions_extras_and_links(self):
        entries = ["One_Pkg>=1", "One.Pkg[ssl]", "Two; extra == 'pdf'",
                   "Three @ https://example.org/file.whl", "four (>=1)"]
        names = names_from_metadata({"info": {"requires_dist": entries}})
        self.assertEqual(names, ("four", "one-pkg", "three", "two"))

    def test_absent_dependencies(self):
        for info in ({}, {"requires_dist": None}, {"requires_dist": []}):
            self.assertEqual(names_from_metadata({"info": info}), ())

    def test_bad_metadata(self):
        for data in ([], {}, {"info": None}, {"info": {"requires_dist": "A"}},
                     {"info": {"requires_dist": ["???"]}}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                names_from_metadata(data)

    @patch("src.repository.urlopen")
    def test_configured_api_and_cache(self, request):
        request.return_value = io.BytesIO(b'{"info":{"requires_dist":["X"]}}')
        fetch = remote_source("https://example.org/mirror/pypi/")
        self.assertEqual(fetch("sample"), ("x",))
        self.assertEqual(fetch("sample"), ("x",))
        request.assert_called_once()
        url = request.call_args.args[0]
        self.assertEqual(url, "https://example.org/mirror/pypi/sample/json")

    @patch("src.repository.urlopen")
    def test_http_and_json_errors_name_the_package(self, request):
        fetch = remote_source("https://example.org")
        request.side_effect = HTTPError("url", 404, "missing", {}, None)
        with self.assertRaisesRegex(ValueError, "sample"):
            fetch("sample")
        request.side_effect = None
        request.return_value = io.BytesIO(b"not json")
        with self.assertRaisesRegex(ValueError, "other"):
            fetch("other")


class GraphTests(unittest.TestCase):
    """Exercise DFS independently of file, network and rendering."""

    def test_shorter_path_reopens_boundary(self):
        data = dict(A="BZ", B="C", C="Z", Z="D", D="E", E="")
        graph = walk("A", data.__getitem__, 3)
        self.assertEqual(graph["Z"], {"D"})
        self.assertEqual(graph["D"], {"E"})

    def test_cycle_and_self_loop(self):
        data = dict(A="AB", B="A")
        self.assertEqual(walk("A", data.get, 100), dict(A={"A", "B"}, B={"A"}))

    def test_zero_depth_does_not_read(self):
        self.assertEqual(walk("A", self.fail, 0), {"A": set()})

    def test_filter_cuts_entire_branch(self):
        data = dict(A="BC", B="D", C="", D="")
        self.assertEqual(walk("A", data.get, 3, "b"), dict(A={"C"}, C=set()))
        self.assertEqual(walk("A", self.fail, 3, "a"), {})

    def test_deep_chain_needs_no_recursion(self):
        length = 2500
        graph = walk(0, lambda node: [node + 1], length)
        self.assertEqual(len(graph), length + 1)

    def test_reverse_uses_entire_test_repository(self):
        data = dict(A="B", B="C", C="B", D="C", E="")
        self.assertEqual(reverse_names("C", data, 2, ""), ["A", "B", "D"])
        self.assertEqual(reverse_names("C", data, 1, ""), ["B", "D"])
        self.assertEqual(reverse_names("C", data, 2, "b"), ["D"])
        self.assertEqual(reverse_names("E", data, 3, ""), [])
