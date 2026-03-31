# bilibiliTools

Python 爬取B站（bilibili.com）UP主的所有视频链接及详细信息

博客：[https://blog.xieqiaokang.com/posts/36033.html](https://blog.xieqiaokang.com/posts/36033.html)

## 功能

根据UID查询该UP的视频并以json格式保存

查找BVJS中的BV号和URL

通过URL将视频保存到指定收藏夹



## 环境准备

根据requirements.txt下载依赖就好

主体功能参照原主链接

https://github.com/xieqk/Bilibili_Spider_by_UserID

本人对原主的功能进行了一定修改

### 特别是本人使用的是chrome浏览器和而原作者使用的是Firefox

chromedriver安装参照[chromedriver安装教程(windows版)_喜欢听歌的二哥的博客-CSDN博客](https://blog.csdn.net/qq_27472133/article/details/128569296)

高版本或者说最新版本的chromedriver下载[Chrome for Testing availability (googlechromelabs.github.io)](https://googlechromelabs.github.io/chrome-for-testing/#stable)

对原主读取逻辑进行了一定的优化，减少了一部分bug



##### 查找BVJS中的BV号和URL

就是简单正则表达式的查询json文本

##### 通过URL将视频保存到指定收藏夹

通过cookie获取登录信息，然后依次点击罢了。



有人问了那下载功能呢？

这就不得不提https://github.com/leiurayer/downkyi 了



说句实话直接下载https://github.com/leiurayer/downkyi 就好。这个下载器支持网页直接获取下载链接所以我费了一整天做好的东西其实人家早搞好了。

## v1 重构骨架

仓库现在同时包含两套内容：

- 旧脚本入口：根目录下的 `main.py`、`BulkBookmarking.py`、`getCookie.py` 等
- 新应用骨架：`src/` 目录，用来承接“抓取 + 下载 + 本地播放器 + 媒体库”

### 新结构

```text
src/
  app.py              # 统一 CLI 入口
  config.py           # 项目路径配置
  crawler/            # 抓取层
  downloader/         # 下载层
  player/             # 播放层
  library/            # SQLite 仓储层
  infra/              # 基础设施
  models/             # 数据模型
  services/           # 应用装配
  gui/                # 桌面壳
```

### 已落地的 v1 能力

- SQLite 本地数据库
- `videos / downloads / media_files / play_history / settings` 五张基础表
- 统一 CLI 入口
- 对旧 `Bilibili_Spider` 的服务化封装
- `yt-dlp` 下载器命令构建器
- `mpv` 播放器命令构建器
- PySide6 最小桌面壳占位

### 使用方式

初始化数据库：

```bash
python -m src.app init-db
```

抓取指定 UID：

```bash
python -m src.app crawl --uid 362548791 --save-json
```

抓取并补全详情：

```bash
python -m src.app crawl --uid 362548791 --detail --save-json
```

查看最近入库的视频：

```bash
python -m src.app list-videos
```

将已入库视频加入下载队列：

```bash
python -m src.app queue-download --url https://www.bilibili.com/video/BVxxxxxxx
```

启动桌面壳：

```bash
python -m src.app desktop
```

### 当前阶段说明

目前 `src/` 还是第一阶段骨架，重点是把项目从脚本集合改造成可扩展工程。真正的下载执行、播放器 IPC 控制、媒体库界面和 Cookie 管理还要继续往这个骨架里填。
