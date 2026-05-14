#!/usr/bin/env python3
"""Checks for obvious architectural violations. See ARCH_DECISIONS.md."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


ALWAYS_EXCLUDE = {"venv", ".venv", "__pycache__", "node_modules", ".git"}

# Lines ending with "# arch-ok" are suppressed. Use only for import-guard stubs that
# cannot be avoided (e.g. preventing OpenAI SDK import-time side effects in test setup).
# Never use to silence a genuine violation.
SUPPRESSION_SUFFIX = "# arch-ok"


def scan(
    glob: str,
    pattern: str,
    exclude_paths: set[str] = frozenset(),
    exclude_dirs: set[str] = frozenset(),
) -> list[tuple[str, int, str]]:
    hits = []
    for path in sorted(ROOT.glob(glob)):
        rel = str(path.relative_to(ROOT))
        if rel in exclude_paths:
            continue
        parts = set(Path(rel).parts)
        if parts & (ALWAYS_EXCLUDE | exclude_dirs):
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if line.rstrip().endswith(SUPPRESSION_SUFFIX):
                continue
            if re.search(pattern, line):
                hits.append((rel, lineno, line.strip()))
    return hits


# Each entry: (description, glob, regex, exclude_paths, exclude_dirs)
CHECKS = [
    (
        "Routers must not import from data_access/ — go through a service instead",
        "routers/*.py",
        r"from data_access",
        set(),
        set(),
    ),
    (
        "boto3.client('s3') must only appear in integrations/s3_service.py",
        "**/*.py",
        r"""boto3\.client\(\s*['"]s3['"]""",
        {"integrations/s3_service.py"},
        {"tests", "scripts"},
    ),
    (
        "os.getenv('MOCK_AI') must only be read in main.py (startup lifespan)",
        "**/*.py",
        r"""getenv\(\s*['"]MOCK_AI['"]""",
        {"main.py"},
        {"tests", "scripts"},
    ),
    (
        "Services must not call get_bot_provider() — the router wires it via Depends()",
        "services/**/*.py",
        r"get_bot_provider",
        set(),
        set(),
    ),
    (
        "Service guard methods must not use assert_ prefix — use check_* or verify_* instead",
        "services/**/*.py",
        r"^\s*def assert_",
        set(),
        set(),
    ),
    (
        "Module-level run_* functions are banned in services/ — wrap logic in a service class",
        "services/**/*.py",
        r"^def run_",
        set(),
        set(),
    ),
    (
        "Tests must not patch get_bot_provider — pass MockBotProvider() via constructor injection",
        "tests/**/*.py",
        r"""patch\(.*get_bot_provider""",
        set(),
        set(),
    ),
    (
        "Tests must not stub bot modules via sys.modules — use MockBotProvider() instead",
        "tests/**/*.py",
        r"""sys\.modules\[.*bots""",
        set(),
        set(),
    ),
]


_DAO_EXEMPT = {"__init__.py", "config.py"}


def check_dao_naming() -> list[tuple[str, str]]:
    """Every file in data_access/ must end in _dao.py (except exemptions)."""
    hits = []
    for path in sorted((ROOT / "data_access").glob("*.py")):
        if path.name in _DAO_EXEMPT:
            continue
        if not path.name.endswith("_dao.py"):
            hits.append((str(path.relative_to(ROOT)), path.name))
    return hits


def main() -> int:
    failed = False
    for description, glob, pattern, exclude_paths, exclude_dirs in CHECKS:
        hits = scan(glob, pattern, exclude_paths, exclude_dirs)
        if hits:
            failed = True
            print(f"\n[ARCH] {description}")
            for rel, lineno, line in hits:
                print(f"  {rel}:{lineno}: {line}")

    dao_hits = check_dao_naming()
    if dao_hits:
        failed = True
        print("\n[ARCH] data_access/ files must end in _dao.py (except __init__.py and config.py)")
        for rel, name in dao_hits:
            print(f"  {rel}: '{name}' does not end in _dao.py")

    if failed:
        print("\nArchitecture violations found. See ARCH_DECISIONS.md.")
        return 1
    print("No architecture violations found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
