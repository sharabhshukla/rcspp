"""Write the Python code blocks of Markdown pages into one file per block, for type checking.

CI runs ``mypy --strict`` and ``pyright`` over the output, so a sample that uses a name the
package does not declare, or calls a method with the wrong arguments, fails the build. Each file
starts with a comment naming the page and the line of its block, and keeps the block's lines at
the same line numbers as in the page, so an error's line number is the page's.

A block is checked on its own, so it imports what it uses. An HTML comment before a block
changes how it is checked, as for the C++ samples (``scripts/extract_cpp_doc_samples.py``); MyST
does not render it, and it may span several lines:

    <!-- docs-check: given STATEMENTS -->  checked after STATEMENTS, the names a fragment takes
                                           from the reader or from an earlier block
                                           (``rg = ResourceGraph()``), separated by ``;``
    <!-- docs-check: skip -->              not checked

usage: python extract_python_doc_samples.py --output <directory> --root <repo> <page.md>...
"""

import argparse
import re
from pathlib import Path

FENCE = re.compile(r"^(\s*)(`{3,})\s*(python|py)\s*$")
MARKER = re.compile(r"<!--\s*docs-check:\s*([\w-]+)(.*?)-->", re.DOTALL)


def blocks(path: Path):
    """Yield (given statements, first line number, lines) for each checked Python block.

    Line numbers are 1-based.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    marker, argument = None, ""
    i = 0
    while i < len(lines):
        if "<!--" in lines[i] and "docs-check:" in lines[i]:
            # A marker may span several lines: read up to the closing "-->".
            comment = lines[i]
            while "-->" not in comment and i + 1 < len(lines):
                i += 1
                comment += " " + lines[i].strip()
            found = MARKER.search(comment)
            if found:
                marker, argument = found.group(1), " ".join(found.group(2).split())
            i += 1
            continue
        fence = FENCE.match(lines[i])
        if not fence:
            if lines[i].strip():
                marker, argument = None, ""
            i += 1
            continue
        indent, ticks = fence.group(1), fence.group(2)
        first = i + 2
        body = []
        i += 1
        while i < len(lines) and lines[i].strip() != ticks:
            body.append(lines[i][len(indent) :] if lines[i].startswith(indent) else lines[i])
            i += 1
        i += 1
        if marker != "skip":
            yield (argument if marker == "given" else ""), first, body
        marker, argument = None, ""


def main() -> int:
    """Extract the blocks of every page given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("pages", type=Path, nargs="+")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    for stale in args.output.glob("*.py"):
        stale.unlink()
    count = 0
    for page in args.pages:
        relative = page.resolve().relative_to(args.root.resolve())
        stem = re.sub(r"\W+", "_", relative.with_suffix("").as_posix())
        for given, first, body in blocks(page):
            header = f"# {relative.as_posix()}:{first} (scripts/extract_python_doc_samples.py)"
            if given:
                # On the first line, so that the block keeps the page's line numbers.
                header = f"{given}  {header}"
            padding = [""] * (first - 2)
            target = args.output / f"{stem}_line_{first}.py"
            target.write_text("\n".join([header, *padding, *body]) + "\n", encoding="utf-8")
            count += 1
    print(f"{count} Python block(s) written to {args.output}")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
