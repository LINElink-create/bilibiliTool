"""Allow `python -m bilibili_tool` to launch the CLI."""

from bilibili_tool.app.main import main


if __name__ == "__main__":
    raise SystemExit(main())

