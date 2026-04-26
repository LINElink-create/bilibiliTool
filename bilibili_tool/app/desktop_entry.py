from __future__ import annotations

from bilibili_tool.application import build_context
from bilibili_tool.gui import run_desktop_app


def main() -> int:
    """Launch the desktop app without requiring CLI arguments."""

    context = build_context()
    context.workspace_service.initialize()
    return run_desktop_app(context)


if __name__ == "__main__":
    raise SystemExit(main())
