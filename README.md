# bilibiliTool

一个面向桌面的 B 站工具，当前重点是：

- 本地登录与会话复用
- 来源录入与基础探测
- 单视频下载

当前主代码位于 [bilibili_tool/](D:/bilibiliTool/bilibiliTool/bilibili_tool)。

## 当前进度

已完成

- 桌面 GUI 主界面，支持中英文切换
- 内嵌浏览器登录，自动捕获并保存本地会话
- 用户来源预览
  - 支持 UID、用户主页链接、用户名输入
- 用户名搜索
  - 不走公开搜索 API
  - 通过浏览器内核访问 B 站搜索页，返回候选 UID 与主页
- 收藏夹来源预览与单次探测
- 收藏夹第一页单次同步到本地资源库
- 单视频下载
  - 支持 BV 号或视频链接
  - 通过 `yt-dlp` 真实下载
  - 已接入 `ffmpeg` 自动合并音视频

未完成

- 按 UP 主批量抓取历史稿件
- 整个收藏夹的批量下载
- 更完整的下载任务调度
  - 暂无暂停、恢复、重试、并发队列管理
- 更深入的资源库与下载联动
  - 例如批量勾选下载、下载后自动归档整理

## 环境要求

- Python `3.11`
- 推荐使用 Conda 环境
- 推荐安装 `ffmpeg`

## 安装

```powershell
conda create -n bilibiliTool python=3.11 -y
conda activate bilibiliTool
python -m pip install -U pip
pip install -r requirements.txt
conda install -n bilibiliTool -c conda-forge ffmpeg -y
```

## 启动

桌面版：

```powershell
conda activate bilibiliTool
python -m bilibili_tool desktop
```

CLI：

```powershell
conda activate bilibiliTool
python -m bilibili_tool --help
```

## 当前可用功能

### 1. 本地登录

- 进入“登录”页后会直接打开 B 站页面
- 程序会监听关键 Cookie
- 当检测到可用会话后，会自动保存到本地
- 已保存的会话会在下次启动时尝试恢复

本地数据位置：

- `data/bilibili_tool.db`
- `data/settings.json`
- `data/browser_profile`
- `downloads/`

### 2. 来源页

支持三类来源：

- `user`
- `favorite`
- `video`

当前行为：

- `user`
  - 可以输入用户名、UID 或主页链接
  - 用户名探测走浏览器搜索页
- `favorite`
  - 可以预览、探测，并同步第一页到本地库
- `video`
  - 可以预览并作为单视频下载输入

### 3. 下载页

支持：

- 输入 BV 号或视频链接
- 直接开始下载
- 查看下载任务状态、进度、输出文件和错误信息

说明：

- 默认格式填 `auto`
- 如果环境里有 `ffmpeg`，程序会自动合并音视频
- 如果没有 `ffmpeg`，程序会退回为分离下载

## 常用命令

查看运行目录：

```powershell
python -m bilibili_tool show-paths
```

预览来源：

```powershell
python -m bilibili_tool preview-source --kind user --value 546195
python -m bilibili_tool preview-source --kind favorite --value https://www.bilibili.com/list/ml123456
python -m bilibili_tool preview-source --kind video --value BV18tGHzoEyW
```

同步收藏夹第一页：

```powershell
python -m bilibili_tool sync-favorite-once --value 收藏夹ID或链接
```

下载单视频：

```powershell
python -m bilibili_tool download-video --value BV18tGHzoEyW --format auto
```

查看下载任务：

```powershell
python -m bilibili_tool list-downloads
```

## 已知限制

- 当前仍是“可用优先”的阶段，不是完整成品
- 用户名搜索依赖浏览器页面结构，后续仍可能需要继续加固
- 下载能力目前重点是单视频，不是批量下载平台
- 部分代码和界面文案还会继续收敛和整理
