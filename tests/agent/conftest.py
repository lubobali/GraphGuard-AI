"""Shared helpers for the agent tests."""

import inspect

import pytest


def _code_words(mod) -> set[str]:
    """Every identifier, attribute and string literal in a module's code (not its docstrings)."""
    import ast

    tree = ast.parse(inspect.getsource(mod))
    docs = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
    }  # fmt: skip
    words = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            words.add(n.id)
        elif isinstance(n, ast.Attribute):
            words.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
            words.add(n.value)
    return words


@pytest.fixture
def code_words():
    return _code_words
