import os


def is_pptx_generation_enabled() -> bool:
    """Return True only when PPTX_GENERATION_ENABLED=true is set in the environment.

    Implemented as a function (not a module-level constant) so tests can
    monkeypatch os.environ cleanly without import-order side effects.
    """
    return os.getenv("PPTX_GENERATION_ENABLED", "false").lower() == "true"
