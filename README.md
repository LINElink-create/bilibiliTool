# bilibiliTool

bilibiliTool 是一个桌面优先的 B 站内容管理工具。当前目标是：通过 UP 主、收藏夹或单视频入口，把公开视频信息同步到本地资源库，并通过可视化界面加入下载队列、选择音视频格式、执行下载。

项目当前不依赖 B 站开放平台 API。用户搜索、UP 主稿件同步等能力优先通过内嵌浏览器访问真实页面完成，以降低公开接口风控和 API 权限不可用带来的影响。

## 当前进度

已完成：

- 桌面 GUI：包含首页、来源、资源库、下载、登录、设置页面，并统一了顶部导航和主要页面风格。
- 本地登录：通过内嵌 Chromium 打开 B 站登录页，登录后保存浏览器会话和关键 Cookie，后续同步与下载会优先复用本地会话。
- 来源管理：支持 `UP 主`、`收藏夹`、`单视频` 三类来源。
- UP 主定位：支持输入 UID、用户主页链接或用户名；用户名搜索不走公开搜索 API，而是通过浏览器页面解析候选用户。
- 内容同步：支持同步 UP 主历史稿件、收藏夹第一页、收藏夹多页，并写入本地资源库。
- 资源库：按来源分组展示视频，支持搜索、查看标题、BV 号、作者、发布时间，并可加入下载队列。
- 下载中心：支持单视频下载、资源库批量入队、任务进度展示、失败重试、取消任务、打开下载目录。
- 格式选择：加入下载前可查看真实可用格式，选择视频流、音频流，并决定是否合并音视频。
- 中英文切换：优先读取本地语言设置，也可在设置页切换。
- Windows 打包：提供 PyInstaller 打包脚本，支持生成可分发目录和 zip 包。

仍未完成或需要继续增强：

- 暂停功能目前不做进程级暂停；未开始的任务可暂停，运行中的任务建议取消后重试。
- 下载队列当前以稳定顺序执行为主，尚未实现多 worker 并发下载。
- UP 主和收藏夹同步依赖 B 站网页结构，若页面结构变化，需要更新解析规则。
- 批量同步需要控制频率，避免短时间大量访问触发风控。
- 下载后的文件整理、重命名模板、字幕/封面/弹幕等扩展能力还未系统化。

## 环境要求

- Python 3.11
- 推荐使用 Conda 环境
- 推荐安装 `ffmpeg`，用于合并音视频

当前开发环境推荐：

```powershell
conda create -n bilibiliTool python=3.11 -y
conda activate bilibiliTool
python -m pip install -U pip
python -m pip install -e .
conda install -c conda-forge ffmpeg -y
```

## 启动桌面版

```powershell
conda activate bilibiliTool
python -m bilibili_tool desktop
```

如果需要确认当前程序会把数据写到哪里：

```powershell
python -m bilibili_tool show-paths
```

常用目录：

- `data/`：SQLite 数据库、设置、登录会话、浏览器配置
- `downloads/`：下载输出
- `logs/`：日志
- `exports/`：导出文件

## 推荐使用流程

1. 打开桌面版，进入“登录”页，使用内嵌浏览器完成 B 站登录。
2. 进入“来源”页，点击“新建来源”，选择 UP 主、收藏夹或单视频。
3. 输入 UID、用户名、主页链接、收藏夹链接、收藏夹 ID、BV 号或视频链接。
4. 先解析来源，确认结果正确后保存。
5. 对 UP 主或收藏夹执行同步，视频会进入本地资源库。
6. 在“资源库”页选择视频或来源分组，加入下载队列。
7. 在弹出的格式窗口中选择视频流、音频流和是否合并。
8. 进入“下载”页开始队列，查看进度和输出位置。

## CLI 常用命令

桌面版是主要入口，CLI 用于调试和自动化。

```powershell
python -m bilibili_tool --help
```

来源预览：

```powershell
python -m bilibili_tool preview-source --kind user --value 546195
python -m bilibili_tool preview-source --kind favorite --value 收藏夹ID或链接
python -m bilibili_tool preview-source --kind video --value BV18tGHzoEyW
```

同步内容：

```powershell
python -m bilibili_tool sync-user-archive --value UID或主页链接 --max-pages 20
python -m bilibili_tool sync-favorite-all --value 收藏夹ID或链接 --max-pages 20
```

查看格式和下载：

```powershell
python -m bilibili_tool list-video-formats --value BV18tGHzoEyW
python -m bilibili_tool download-video --value BV18tGHzoEyW --format auto
```

下载队列：

```powershell
python -m bilibili_tool list-downloads
python -m bilibili_tool run-download-queue --limit 5
python -m bilibili_tool retry-download --task-id 1
python -m bilibili_tool cancel-download --task-id 1
```

## 风控和登录说明

- 不建议短时间反复同步同一个 UP 主或收藏夹。
- 程序会尽量复用本地浏览器会话，而不是频繁直接请求公开 API。
- 登录信息只保存在本机 `data/` 目录内，不要把 `data/` 目录发给别人。
- 如果 B 站页面结构或登录策略变化，可能需要更新浏览器解析逻辑。

## Windows 打包

```powershell
conda activate bilibiliTool
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```

打包完成后会生成：

- `dist\bilibiliTool\bilibiliTool.exe`
- `dist\bilibiliTool-windows.zip`

发布给其他人时，优先发送 `dist\bilibiliTool-windows.zip`。对方解压后运行 `bilibiliTool.exe` 即可。

## 未来规划

短期优先级：

- 继续稳定来源页、资源库页和下载页的交互细节。
- 优化批量同步过程的进度展示、取消机制和错误恢复。
- 完善下载格式选择体验，让普通用户更容易理解“视频流、音频流、合并”的区别。
- 增强文件命名和目录归档规则，例如按 UP 主、收藏夹、发布时间自动整理。

中期目标：

- 增加封面、字幕、弹幕、简介等可选下载项。
- 为批量下载加入更清晰的任务分组和失败原因统计。
- 建立更完整的本地测试数据和 UI 回归测试，减少改 UI 时按钮失效的问题。
- 支持更安全的低频同步策略，例如节流、随机等待、断点续同步。

长期方向：

- 形成一个稳定的“B 站个人内容归档工具”：能管理来源、同步元数据、筛选资源、批量下载，并尽量用清晰的可视化界面完成复杂操作。

## 本地验证

运行不访问 B 站的单元测试：

```powershell
python -m unittest discover -s tests -v
```

检查 Python 文件语法：

```powershell
python -m compileall -q bilibili_tool
```
