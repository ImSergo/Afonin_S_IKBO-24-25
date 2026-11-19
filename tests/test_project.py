"""Integration checks for stages and all user-facing parameters."""

import ast
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.__main__ import main
from src.graph import PNG_SIGNATURE, renderer_path, reverse_names, walk
from src.repository import local_graph, names_from_metadata, remote_source


SAMPLE = str(Path(__file__).resolve().parents[1] / "examples/repository.json")
BASE = ["-t", "-p", "A", "-r", SAMPLE]


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
    """Verify observable behavior, not implementation details."""

    def test_configuration(self):
        status, output, _ = invoke(BASE + ["--show-config"])
        self.assertEqual(status, 0)
        for field in ("package=A", "repo=", "test_mode=True", "output=",
                      "max_depth=3", "filter="):
            self.assertIn(field, output)

    def test_parameter_errors(self):
        cases = [[], ["-p", "A!"], ["-r", "no-url"], ["-d", "-1"],
                 ["-d", "many"], ["-o", "x.svg"], ["-f", "  "],
                 ["-t"], ["--test-mode=yes"], ["--reverse"],
                 ["--direct-only", "--reverse"], ["--scope", "A"]]
        for flags in cases:
            args = ["-p", "foo", *flags] if flags else []
            with self.subTest(flags=flags):
                status, _, message = invoke(args)
                self.assertEqual(status, 2)
                self.assertTrue(message)

    def test_package_not_found(self):
        status, _, message = invoke([*BASE, "-p", "ZZ", "--graph-only"])
        self.assertEqual(status, 1)
        self.assertIn("ZZ", message)

    def test_direct_reverse_and_empty_result(self):
        self.assertEqual(invoke(BASE + ["--direct-only"])[1], "B\nC\n")
        flags = [*BASE, "-p", "D", "--reverse", "-d", "1"]
        self.assertEqual(invoke(flags)[1], "B\nC\nF\n")
        self.assertFalse(invoke(BASE + ["-p", "G", "--reverse"])[1].strip())

    @patch("src.__main__.remote_source")
    def test_remote_reverse_scope(self, source):
        source.return_value = {"a": ["b"], "b": ["c"], "c": []}.get
        args = ["-p", "C", "--scope", "A", "--reverse"]
        self.assertEqual(invoke(args)[:2], (0, "a\nb\n"))

    def test_dot_only(self):
        status, text, _ = invoke(BASE + ["--graph-only", "-d", "0"])
        self.assertEqual(status, 0)
        self.assertEqual(text, 'digraph dependencies {\n  rankdir=LR;\n'
                         '  "A";\n}\n')

    def test_missing_renderer_leaves_no_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "graph.png")
            with patch.dict(os.environ, GRAPHVIZ_DOT="no-such-graphviz-dot"):
                status, _, message = invoke([*BASE, "-o", str(output)])
            self.assertEqual(status, 1)
            self.assertIn("Graphviz", message)
            self.assertFalse(output.exists())

    @unittest.skipUnless(shutil.which(renderer_path()),
                         "Graphviz is not installed")
    def test_png_and_dot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "nested", "cycle.png")
            status, text, message = invoke([*BASE, "-o", str(output)])
            self.assertEqual(status, 0, message)
            self.assertTrue(output.read_bytes().startswith(PNG_SIGNATURE))
            self.assertEqual(output.with_suffix(".dot").read_text(), text)
            self.assertIn('"D" -> "B"', text)


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

    def test_local_validation_and_implicit_leaf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "repo.json")
            path.write_text('{"A": ["B", "B"]}', encoding="utf-8-sig")
            self.assertEqual(local_graph(path), {"A": ("B",), "B": ()})
            for text in ('[]', '{"a": []}', '{"A": "B"}', '{"A": [2]}'):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    local_graph(path)


ROOT = Path(__file__).resolve().parents[1]
FILE_LIMIT = 1000
LINE_LIMIT = 80
FUNCTION_LIMIT = 40
ARGUMENT_LIMIT = 7


class LayoutTests(unittest.TestCase):
    """Keep repository conventions under continuous test."""

    def test_required_files(self):
        for name in ("README.md", ".gitignore", "src", "tests", "run.bat"):
            self.assertTrue((ROOT / name).exists(), name)

    def test_python_limits(self):
        for folder in (ROOT / "src", ROOT / "tests"):
            for path in folder.rglob("*.py"):
                with self.subTest(file=path.name):
                    self.check_source(path)

    def check_source(self, path):
        """Check text width, function spans and parameter counts."""
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        self.assertLessEqual(len(lines), FILE_LIMIT)
        for number, line in enumerate(lines, 1):
            self.assertLessEqual(len(line), LINE_LIMIT, f"{path}:{number}")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                size = node.end_lineno - node.lineno + 1
                params = node.args
                positional = params.args + params.posonlyargs
                count = len(positional + params.kwonlyargs)
                count += bool(params.vararg) + bool(params.kwarg)
                self.assertLessEqual(size, FUNCTION_LIMIT, node.name)
                self.assertLessEqual(count, ARGUMENT_LIMIT, node.name)
