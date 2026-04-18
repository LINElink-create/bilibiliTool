from __future__ import annotations

import argparse

from bilibili_tool.application import build_context
from bilibili_tool.domain import SourceKind


def build_parser() -> argparse.ArgumentParser:
    """定义当前阶段的 CLI，覆盖登录、来源预览、单次探测和单次同步。"""

    parser = argparse.ArgumentParser(description="bilibiliTool greenfield CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create the workspace folders and initialize the SQLite database.")
    subparsers.add_parser("show-paths", help="Print runtime workspace paths.")
    subparsers.add_parser("login-status", help="Print the current local login session state.")
    subparsers.add_parser("qr-login-preview", help="Print the planned QR login flow without contacting bilibili.")
    subparsers.add_parser("qr-login-init", help="Call bilibili once to initialize a QR login flow.")

    poll_qr_parser = subparsers.add_parser("qr-login-poll", help="Poll the current QR login state once.")
    poll_qr_parser.add_argument("--key", required=True, help="The qrcode_key returned by qr-login-init.")

    save_session_parser = subparsers.add_parser("save-session", help="Save a local cookie session for future sync/download work.")
    save_session_parser.add_argument("--name", required=True, help="Local session name shown in the UI.")
    save_session_parser.add_argument("--cookie-json", required=True, help="Cookie JSON string collected from a browser or login flow.")
    save_session_parser.add_argument("--csrf", help="Optional bili_jct token stored with the session.")

    add_source_parser = subparsers.add_parser("add-source", help="Register a source to be synced later.")
    add_source_parser.add_argument("--kind", choices=[kind.value for kind in SourceKind], required=True)
    add_source_parser.add_argument("--value", required=True, help="UID, favorite ID, BV, username, or a supported bilibili URL.")
    add_source_parser.add_argument("--name", help="Optional display name shown in the desktop UI.")

    preview_source_parser = subparsers.add_parser("preview-source", help="Preview how a source input will be resolved locally.")
    preview_source_parser.add_argument("--kind", choices=[kind.value for kind in SourceKind], required=True)
    preview_source_parser.add_argument("--value", required=True, help="UID, favorite ID, BV, username, or a supported bilibili URL.")
    preview_source_parser.add_argument("--name", help="Optional display name shown in the preview.")

    probe_user_parser = subparsers.add_parser("probe-user", help="Probe a username or UID with a single real bilibili request.")
    probe_user_parser.add_argument("--value", required=True, help="A username, UID, or user homepage URL.")

    probe_favorite_parser = subparsers.add_parser("probe-favorite", help="Validate a favorite link or ID with a single real bilibili request.")
    probe_favorite_parser.add_argument("--value", required=True, help="A favorite ID or favorite URL.")

    sync_favorite_parser = subparsers.add_parser("sync-favorite-once", help="Fetch the first page of a favorite and write it into the local library.")
    sync_favorite_parser.add_argument("--value", required=True, help="A favorite ID or favorite URL.")
    sync_favorite_parser.add_argument("--name", help="Optional display name used for the saved source.")

    subparsers.add_parser("list-sources", help="List all tracked sources.")
    subparsers.add_parser("list-videos", help="List recent cached videos.")
    subparsers.add_parser("list-downloads", help="List queued download tasks.")

    queue_download_parser = subparsers.add_parser("queue-download", help="Queue a direct download URL for later.")
    queue_download_parser.add_argument("--url", required=True, help="Video URL that will later be handled by yt-dlp.")
    queue_download_parser.add_argument("--name", required=True, help="Human-readable task name.")
    queue_download_parser.add_argument("--format", default="auto", help="yt-dlp format selector. Use auto to let yt-dlp decide.")

    download_video_parser = subparsers.add_parser("download-video", help="Download a single BV id or video URL immediately.")
    download_video_parser.add_argument("--value", required=True, help="A BV id or bilibili video URL.")
    download_video_parser.add_argument("--name", help="Optional display name shown in the downloads table.")
    download_video_parser.add_argument("--format", default="auto", help="yt-dlp format selector. Use auto to let yt-dlp decide.")

    list_formats_parser = subparsers.add_parser("list-video-formats", help="Inspect the real formats available for one BV id or video URL.")
    list_formats_parser.add_argument("--value", required=True, help="A BV id or bilibili video URL.")

    subparsers.add_parser("desktop", help="Launch the desktop shell.")
    return parser


def command_init_db() -> int:
    """初始化工作目录和数据库。"""

    context = build_context()
    path = context.workspace_service.initialize()
    print(f"Database initialized at {path}")
    return 0


def command_show_paths() -> int:
    """打印运行期路径，方便确认输出位置。"""

    context = build_context()
    context.workspace_service.initialize()
    print(f"root={context.paths.root}")
    print(f"data={context.paths.data_dir}")
    print(f"logs={context.paths.logs_dir}")
    print(f"exports={context.paths.exports_dir}")
    print(f"downloads={context.paths.downloads_dir}")
    print(f"browser_profile={context.paths.browser_profile_dir}")
    print(f"database={context.paths.database_path}")
    print(f"settings={context.paths.settings_path}")
    return 0


def command_login_status() -> int:
    """打印当前本地登录态。"""

    context = build_context()
    context.workspace_service.initialize()
    state = context.auth_service.get_login_state()
    print(f"logged_in={state.is_logged_in}")
    print(f"session_name={state.session_name}")
    print(f"message={state.display_message}")
    return 0


def command_qr_login_preview() -> int:
    """打印二维码登录流程预览。"""

    context = build_context()
    context.workspace_service.initialize()
    draft = context.auth_service.build_qr_login_draft()
    print(draft.title)
    print(draft.summary)
    for index, step in enumerate(draft.steps, start=1):
        print(f"{index}. {step.name} [{step.method}]")
        print(f"   url={step.url}")
        print(f"   purpose={step.purpose}")
    return 0


def command_qr_login_init() -> int:
    """真实请求一次二维码初始化接口。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.auth_service.init_qr_login()
    print(f"success={result.success}")
    print(f"message={result.message}")
    print(f"qrcode_key={result.qrcode_key}")
    print(f"qrcode_url={result.qrcode_url}")
    return 0


def command_qr_login_poll(qrcode_key: str) -> int:
    """真实查询一次二维码当前状态。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.auth_service.poll_qr_login(qrcode_key)
    print(f"success={result.success}")
    print(f"status_code={result.status_code}")
    print(f"message={result.message}")
    print(f"redirect_url={result.redirect_url}")
    print(f"refresh_token={result.refresh_token}")
    return 0


def command_save_session(session_name: str, cookie_json: str, csrf: str | None) -> int:
    """保存本地会话，供后续登录落库复用。"""

    context = build_context()
    context.workspace_service.initialize()
    session_id = context.auth_service.save_session(session_name=session_name, cookie_json=cookie_json, csrf=csrf)
    print(f"Auth session #{session_id} saved.")
    return 0


def command_preview_source(kind: str, value: str, name: str | None) -> int:
    """打印来源输入的本地解析预览。"""

    context = build_context()
    context.workspace_service.initialize()
    preview = context.source_service.preview_source(kind=SourceKind(kind), raw_value=value, display_name=name)
    print(f"kind={preview.kind.value}")
    print(f"input_mode={preview.input_mode}")
    print(f"display_name={preview.display_name}")
    print(f"resolved_key={preview.resolved_key}")
    print(f"canonical_url={preview.canonical_url}")
    print(f"is_ready_for_save={preview.is_ready_for_save}")
    print(f"message={preview.message}")
    print(f"next_step={context.source_service.describe_next_sync_step(preview)}")
    return 0


def command_probe_user(value: str) -> int:
    """对用户名或 UID 做一次真实探测。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.source_service.probe_user_input(raw_value=value)
    print(f"success={result.success}")
    print(f"input_mode={result.input_mode}")
    print(f"input_value={result.input_value}")
    print(f"message={result.message}")
    if result.items:
        for item in result.items:
            print(f"item={item}")
    return 0


def command_probe_favorite(value: str) -> int:
    """对收藏夹输入做一次真实校验。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.source_service.probe_favorite_input(raw_value=value)
    print(f"success={result.success}")
    print(f"favorite_id={result.favorite_id}")
    print(f"title={result.title}")
    print(f"owner_name={result.owner_name}")
    print(f"media_count={result.media_count}")
    print(f"message={result.message}")
    return 0


def command_sync_favorite_once(value: str, name: str | None) -> int:
    """把收藏夹第一页同步进本地资源库。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.source_service.sync_favorite_once(raw_value=value, display_name=name)
    print(f"success={result.success}")
    print(f"source_id={result.source_id}")
    print(f"source_name={result.source_name}")
    print(f"message={result.message}")
    print(f"synced_count={result.synced_count}")
    print(f"new_count={result.new_count}")
    print(f"updated_count={result.updated_count}")
    return 0


def command_add_source(kind: str, value: str, name: str | None) -> int:
    """写入一个新的来源配置。"""

    context = build_context()
    context.workspace_service.initialize()
    source_id = context.source_service.add_source(kind=SourceKind(kind), raw_value=value, display_name=name)
    print(f"Source #{source_id} saved.")
    return 0


def command_list_sources() -> int:
    """打印来源清单。"""

    context = build_context()
    context.workspace_service.initialize()
    sources = context.source_service.list_sources()
    if not sources:
        print("No sources configured yet.")
        return 0

    for source in sources:
        print(f"[{source.id}] {source.kind.value} | {source.display_name} | {source.url}")
    return 0


def command_list_videos() -> int:
    """打印资源库当前视频。"""

    context = build_context()
    context.workspace_service.initialize()
    videos = context.library_service.list_videos(limit=50)
    if not videos:
        print("No videos cached yet.")
        return 0

    for video in videos:
        print(f"[{video.id}] {video.bvid} | {video.title} | {video.owner_name or '-'}")
    return 0


def command_queue_download(url: str, name: str, format_selector: str) -> int:
    """把下载请求写入下载队列。"""

    context = build_context()
    context.workspace_service.initialize()
    task_id = context.download_service.queue_url(url=url, display_name=name, format_selector=format_selector)
    print(f"Download task #{task_id} queued.")
    return 0


def command_download_video(value: str, name: str | None, format_selector: str) -> int:
    """解析单视频输入并立刻执行下载。"""

    context = build_context()
    context.workspace_service.initialize()
    preview = context.source_service.preview_source(kind=SourceKind.VIDEO, raw_value=value, display_name=name)
    task = context.download_service.download_now(
        url=preview.canonical_url or value,
        display_name=name or preview.display_name,
        format_selector=format_selector,
    )
    print(f"task_id={task.id}")
    print(f"status={task.status.value}")
    print(f"file_path={task.file_path}")
    print(f"error_message={task.error_message}")
    return 0 if task.status.value == "success" else 1


def command_list_video_formats(value: str) -> int:
    """列出单视频当前可用的真实格式。"""

    context = build_context()
    context.workspace_service.initialize()
    result = context.download_service.probe_video_formats(raw_value=value)
    print(f"title={result.title}")
    print(f"source_url={result.source_url}")
    print(f"format_count={len(result.formats)}")
    for item in result.formats:
        print(
            " | ".join(
                [
                    f"format_id={item.format_id}",
                    f"ext={item.ext or '-'}",
                    f"resolution={item.resolution or '-'}",
                    f"vcodec={item.vcodec or '-'}",
                    f"acodec={item.acodec or '-'}",
                    f"protocol={item.protocol or '-'}",
                    f"filesize={item.filesize_text or '-'}",
                    f"note={item.note or '-'}",
                ]
            )
        )
    return 0


def command_list_downloads() -> int:
    """打印下载队列。"""

    context = build_context()
    context.workspace_service.initialize()
    tasks = context.download_service.list_tasks(limit=50)
    if not tasks:
        print("No download tasks queued yet.")
        return 0

    for task in tasks:
        print(f"[{task.id}] {task.status.value} | {task.display_name} | {task.source_url}")
    return 0


def main() -> int:
    """CLI 主入口。"""

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        return command_init_db()
    if args.command == "show-paths":
        return command_show_paths()
    if args.command == "login-status":
        return command_login_status()
    if args.command == "qr-login-preview":
        return command_qr_login_preview()
    if args.command == "qr-login-init":
        return command_qr_login_init()
    if args.command == "qr-login-poll":
        return command_qr_login_poll(qrcode_key=args.key)
    if args.command == "save-session":
        return command_save_session(session_name=args.name, cookie_json=args.cookie_json, csrf=args.csrf)
    if args.command == "preview-source":
        return command_preview_source(kind=args.kind, value=args.value, name=args.name)
    if args.command == "probe-user":
        return command_probe_user(value=args.value)
    if args.command == "probe-favorite":
        return command_probe_favorite(value=args.value)
    if args.command == "sync-favorite-once":
        return command_sync_favorite_once(value=args.value, name=args.name)
    if args.command == "add-source":
        return command_add_source(kind=args.kind, value=args.value, name=args.name)
    if args.command == "list-sources":
        return command_list_sources()
    if args.command == "list-videos":
        return command_list_videos()
    if args.command == "queue-download":
        return command_queue_download(url=args.url, name=args.name, format_selector=args.format)
    if args.command == "download-video":
        return command_download_video(value=args.value, name=args.name, format_selector=args.format)
    if args.command == "list-video-formats":
        return command_list_video_formats(value=args.value)
    if args.command == "list-downloads":
        return command_list_downloads()
    if args.command == "desktop":
        from bilibili_tool.gui import run_desktop_app

        context = build_context()
        context.workspace_service.initialize()
        return run_desktop_app(context)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
