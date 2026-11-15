"""Regenerate the type stubs of the compiled extension, ``rcspp._core``.

Run from the repository root, with the extension built and importable::

    pip install pybind11-stubgen black isort
    PYTHONPATH=python/src python scripts/generate_stubs.py

The stubs are written to ``python/src/rcspp/_core/``. CI checks them against the
extension with ``python -m mypy.stubtest rcspp._core``, so regenerate them after any
change to the bindings. The script fails when a signature names a C++ type that is not
bound, which means a type is bound after a function that uses it.
"""

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Where each enum lives, so that default values print as Python expressions.
ENUM_LOCATIONS = {
    "LogLevel": "rcspp._core.logger",
    "SearchDirection": "rcspp._core.graph",
    "Algorithm": "rcspp._core.graph",
}


# A binding that takes or returns a bare py::dict, py::tuple or py::function is written as a bare
# `dict`, `tuple` or `Callable`, whose parameters a type checker reports as unknown wherever the
# name is used. They are spelled out as "anything", which is what the binding accepts.
BARE_GENERICS = (
    (
        re.compile(r"\bcollections\.abc\.Callable\b(?!\[)"),
        "collections.abc.Callable[..., typing.Any]",
    ),
    (re.compile(r"(?<=[:>] )dict\b(?!\[)"), "dict[typing.Any, typing.Any]"),
    (re.compile(r"(?<=[:>] )tuple\b(?!\[)"), "tuple[typing.Any, ...]"),
)


def spell_out_bare_generics(path: pathlib.Path) -> None:
    """Give the bare generic types of a stub their parameters, in annotations only."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    in_docstring = False
    for i, line in enumerate(lines):
        quotes = line.count('"""')
        if in_docstring or quotes:
            if quotes % 2:
                in_docstring = not in_docstring
            continue
        for pattern, replacement in BARE_GENERICS:
            line = pattern.sub(replacement, line)
        lines[i] = line
    text = "".join(lines)
    if "typing.Any" in text and not re.search(r"^import typing$", text, re.MULTILINE):
        raise SystemExit(f"{path}: uses typing.Any but does not import typing")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    """Run pybind11-stubgen on rcspp._core, writing into python/src."""
    command = [
        sys.executable,
        "-m",
        "pybind11_stubgen",
        "rcspp._core",
        "--output-dir",
        str(ROOT / "python" / "src"),
        "--exit-code",
    ]
    for enum, location in ENUM_LOCATIONS.items():
        command += ["--enum-class-locations", f"{enum}:{location}"]
    status = subprocess.call(command)  # nosec B603 - fixed arguments
    if status != 0:
        return status
    # Format them as pre-commit would, so that regenerating them changes only what changed.
    stubs = [
        str(path) for path in sorted((ROOT / "python" / "src" / "rcspp" / "_core").glob("*.pyi"))
    ]
    for stub in stubs:
        spell_out_bare_generics(pathlib.Path(stub))
    for formatter in ("isort", "black"):
        status = subprocess.call([sys.executable, "-m", formatter, "-q", *stubs])  # nosec B603
        if status != 0:
            return status
    return 0


if __name__ == "__main__":
    sys.exit(main())
