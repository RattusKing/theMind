"""The rules that hold the build together, checked by machine instead of memory.

    python3 tests/guards.py

Three guards, each one a promise the project makes that a single careless
commit could break silently and permanently:

  1. The retired name. The product theMind grew out of is never named — not in
     code, docs, tests, or commit messages. This guard holds the name only as a
     hash, so the guard itself never carries it. Every word in every tracked
     file and every commit message is checked, camelCase and snake_case split
     apart. Text from outside the repo (a pull request's title and body) can be
     passed in THEMIND_GUARD_TEXT.
  2. Pure stdlib. Nothing under themind/ or tests/ imports anything that is not
     the standard library or theMind itself. The host brings its own SDK; the
     library never does. (examples/ is host code and is exempt.)
  3. Zero dependencies. pyproject.toml declares none.

Exits 0 when every guard holds, 1 otherwise. Never prints the name it guards.
Needs Python 3.11+ (sys.stdlib_module_names, tomllib); the suite itself runs
on 3.9+.
"""
import ast
import hashlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETIRED = "fb2cb45b6b443241e38145b6445a6e0ebee0410d19e71d9fd0adf5fc382d49e5"  # sha256, lowercase
OWN_CODE = ("themind", "tests")

_PLAIN = re.compile(r"[A-Za-z]+")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")


def _named(text):
    """True if the retired name appears as a word, in any case or casing style."""
    for word in set(_PLAIN.findall(text)) | set(_CAMEL.findall(text)):
        if hashlib.sha256(word.lower().encode()).hexdigest() == RETIRED:
            return True
    return False


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def retired_name():
    found = []
    # Tracked files and new ones not yet added, so a local run catches it before
    # the commit does; ignored files are not the repo's and are skipped.
    for rel in _git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0"):
        if not rel:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if _named(line):
                found.append("%s:%d" % (rel, n))
    for entry in _git("log", "--format=%H%x00%B%x1e", "HEAD").split("\x1e"):
        sha, _, body = entry.strip().partition("\0")
        if sha and _named(body):
            found.append("commit %s" % sha[:12])
    if _named(os.environ.get("THEMIND_GUARD_TEXT", "")):
        found.append("pull request title or description")
    return ["the retired name appears in " + where for where in found]


def pure_stdlib():
    allowed = set(sys.stdlib_module_names) | {"themind"}
    found = []
    for top in OWN_CODE:
        for path in sorted((ROOT / top).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as e:
                found.append("%s:%s could not be parsed, so its imports are unchecked"
                             % (path.relative_to(ROOT), e.lineno))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.split(".")[0] not in allowed:
                        found.append("%s:%d imports %s, which is not the standard library"
                                     % (path.relative_to(ROOT), node.lineno, name))
    return found


def zero_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    found = []
    if project.get("dependencies"):
        found.append("pyproject.toml declares dependencies: %s" % project["dependencies"])
    if project.get("optional-dependencies"):
        found.append("pyproject.toml declares optional dependencies")
    return found


def main():
    failures = 0
    for label, guard in (("retired name", retired_name), ("pure stdlib", pure_stdlib),
                         ("zero dependencies", zero_dependencies)):
        problems = guard()
        print("%s %s" % ("ok  " if not problems else "FAIL", label))
        for p in problems:
            print("       " + p)
        failures += bool(problems)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
