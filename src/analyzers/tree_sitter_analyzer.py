"""Multi-language AST parsing with tree-sitter and LanguageRouter."""

from __future__ import annotations

import pathlib
from typing import Any, Iterator, Tuple

from tree_sitter import Language, Node, Parser, Tree


class LanguageRouter:
    """Select tree-sitter grammar by file extension."""

    def __init__(self) -> None:
        from tree_sitter_language_pack import get_language

        self._get_language = get_language

    def for_path(self, path: pathlib.Path) -> Tuple[str, Language] | None:
        ext = path.suffix.lower()
        if ext == ".py":
            return "python", self._get_language("python")
        if ext == ".sql":
            return "sql", self._get_language("sql")
        if ext in {".yml", ".yaml"}:
            return "yaml", self._get_language("yaml")
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            try:
                return "javascript", self._get_language("javascript")
            except Exception:
                return None
        return None


class TreeSitterAnalyzer:
    """
    Language-agnostic AST parsing. Extracts imports, functions, classes per file.
    """

    def __init__(self, repo_root: pathlib.Path) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.router = LanguageRouter()

    def parse_file(self, path: pathlib.Path) -> Tuple[str, Tree, bytes] | None:
        """Return (language_name, tree, source_bytes) or None if not supported."""
        lang_info = self.router.for_path(path)
        if not lang_info:
            return None
        lang_name, language = lang_info
        try:
            source = path.read_bytes()
        except OSError:
            return None
        parser = Parser(language)
        tree = parser.parse(source)
        return lang_name, tree, source

    def extract_python_imports(self, path: pathlib.Path) -> list[tuple[str, bool]]:
        """(module_name, is_relative) from import/from statements. Relative = from .x.y."""
        result = self.parse_file(path)
        if not result or result[0] != "python":
            return []
        _, tree, source = result
        out: list[tuple[str, bool]] = []

        def node_text(node: Node) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def walk(node: Node) -> None:
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        out.append((node_text(child), False))
                        break
            elif node.type == "import_from_statement":
                # module_name can be dotted_name or relative_import (e.g. ".")
                mod_node = node.child_by_field_name("module_name")
                if mod_node:
                    mod_text = node_text(mod_node)
                    out.append((mod_text, mod_text.startswith(".")))
                else:
                    rel = node.child_by_field_name("relative_import")
                    if rel:
                        mod_text = node_text(rel)
                        out.append((mod_text, True))
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return out

    def extract_python_public_symbols(
        self, path: pathlib.Path
    ) -> Iterator[dict[str, Any]]:
        """Yield dicts with qualified_name, kind (function|class), signature snippet."""
        result = self.parse_file(path)
        if not result or result[0] != "python":
            return
        _, tree, source = result

        def node_text(node: Node) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        rel = str(path.relative_to(self.repo_root))
        prefix = rel.replace("/", ".").replace("\\", ".").removesuffix(".py")

        def walk(node: Node, parent_prefix: str = "") -> Iterator[dict[str, Any]]:
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node and not node_text(name_node).startswith("_"):
                    params = node.child_by_field_name("parameters")
                    sig = node_text(params) if params else ""
                    qual = f"{parent_prefix}.{node_text(name_node)}" if parent_prefix else node_text(name_node)
                    yield {"qualified_name": qual, "kind": "function", "signature": sig[:200]}
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node and not node_text(name_node).startswith("_"):
                    class_name = node_text(name_node)
                    qual = f"{parent_prefix}.{class_name}" if parent_prefix else class_name
                    yield {"qualified_name": qual, "kind": "class", "signature": f"class {class_name}"}
                    for child in node.children:
                        if child.type in ("function_definition", "class_definition"):
                            yield from walk(child, qual)
            for child in node.children:
                if child.type not in ("function_definition", "class_definition"):
                    yield from walk(child, parent_prefix)

        yield from walk(tree.root_node, prefix)

    def iter_python_files(self) -> Iterator[pathlib.Path]:
        """Iterate Python files under repo_root, skipping venv/.git."""
        skip = {"venv", ".venv", "env", ".git", ".cartography", "node_modules"}
        for p in self.repo_root.rglob("*.py"):
            if any(part in skip for part in p.parts):
                continue
            yield p

    def iter_sql_files(self) -> Iterator[pathlib.Path]:
        skip = {".git", ".cartography", "node_modules"}
        for p in self.repo_root.rglob("*.sql"):
            if any(part in skip for part in p.parts):
                continue
            yield p

    def iter_yaml_files(self) -> Iterator[pathlib.Path]:
        skip = {".git", ".cartography", "node_modules"}
        for ext in ("*.yml", "*.yaml"):
            for p in self.repo_root.rglob(ext):
                if any(part in skip for part in p.parts):
                    continue
                yield p
