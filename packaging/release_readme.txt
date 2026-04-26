bilibiliTool Windows Release

How to run:
1. Extract the whole zip package to a writable folder.
2. Double-click bilibiliTool.exe.
3. Do not move bilibiliTool.exe out of this folder by itself.

Runtime folders:
- data: local settings, login session, SQLite database, browser profile
- downloads: downloaded videos
- logs: application logs
- exports: exported files

Notes:
- The package already includes Python dependencies and ffmpeg/ffprobe when they were found during packaging.
- If the app cannot start, keep the whole folder structure intact and try extracting to a path without special permissions, such as Desktop or D:\Apps\bilibiliTool.
- User login cookies are stored only in the local data folder.
