from __future__ import annotations

import sys

DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[0;34m"
RESET = "\033[0m"

_SUPPORTS_COLOR: bool | None = None


def color_supported() -> bool:
    global _SUPPORTS_COLOR
    if _SUPPORTS_COLOR is None:
        _SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return _SUPPORTS_COLOR


def c(code: str, text: str) -> str:
    if not color_supported():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return c("32", t)


def red(t: str) -> str:
    return c("31", t)


def yellow(t: str) -> str:
    return c("1;33", t)


def cyan(t: str) -> str:
    return c("36", t)


def dim(t: str) -> str:
    return c("2", t)


def bold(t: str) -> str:
    return c("1", t)


def confirm(message: str) -> bool:
    raw = input(f"{message} [y/N]: ").strip().lower()
    return raw in ("y", "yes")


def prompt(message: str, default: str = "") -> str:
    if default:
        raw = input(f"  {message} [{default}]: ").strip()
        return raw if raw else default
    else:
        return input(f"  {message}: ").strip()
