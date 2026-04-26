from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import quote

from bilibili_tool.domain import FavoriteFetchResult, VideoRecord


@dataclass(slots=True)
class BrowserUserArchiveScraper:
    """通过 Qt WebEngine 渲染 UP 主投稿页，再从页面 DOM 提取视频。"""

    user_agent: str
    poll_attempts: int = 24
    poll_interval_ms: int = 900
    load_timeout_ms: int = 30000
    cookies: dict[str, str] = field(default_factory=dict)

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """更新渲染投稿页时要带上的 B 站 Cookie。"""

        self.cookies = {key: value for key, value in cookies.items() if value}

    def fetch_page(self, uid: str, *, page: int = 1, page_size: int = 30) -> FavoriteFetchResult:
        """访问空间投稿网页，提取当前页可见的视频卡片。"""

        normalized_uid = uid.strip()
        if not normalized_uid:
            raise ValueError("UID cannot be empty.")

        # 新版空间的真实投稿列表在 /upload/video 下；旧的 /video 路由经常只渲染外壳。
        # 直接打开投稿页，再用页面自己的分页按钮翻页，避免主页推荐区和投稿区混在一起。
        url = f"https://space.bilibili.com/{quote(normalized_uid)}/upload/video"
        collect_limit = max(page_size, 60)
        try:
            payload = self._load_and_collect(
                url=url,
                script=self._build_video_page_script(limit=collect_limit, target_page=page),
                is_complete=lambda payload: self._payload_ready(payload, target_page=page),
            )
        except RuntimeError as exc:
            return FavoriteFetchResult(
                success=False,
                favorite_id=normalized_uid,
                title=None,
                owner_name=None,
                message=f"UP 主投稿网页抓取失败：{exc}",
                videos=(),
            )

        body_text = str(payload.get("bodyText") or "")
        if payload.get("navigationPending"):
            return FavoriteFetchResult(
                success=False,
                favorite_id=normalized_uid,
                title=self._extract_title(payload, normalized_uid),
                owner_name=self._extract_owner_name(payload),
                message=f"投稿网页已打开，但未能切换到第 {page} 页；未写入可能重复或错误的页面内容。",
                videos=(),
            )
        current_page = payload.get("currentPage")
        if page > 1 and isinstance(current_page, (int, float)) and int(current_page) != page:
            return FavoriteFetchResult(
                success=False,
                favorite_id=normalized_uid,
                title=self._extract_title(payload, normalized_uid),
                owner_name=self._extract_owner_name(payload),
                message=f"投稿网页仍停留在第 {int(current_page)} 页，未能切换到第 {page} 页。",
                videos=(),
            )
        if page == 1 and "代表作" in body_text and "最新发布" not in body_text:
            return FavoriteFetchResult(
                success=False,
                favorite_id=normalized_uid,
                title=self._extract_title(payload, normalized_uid),
                owner_name=self._extract_owner_name(payload),
                message="投稿网页没有渲染“最新发布”视频区；为避免把代表作或合集误当投稿，已停止同步。",
                videos=(),
            )

        videos = self._build_videos(payload, uid=normalized_uid)
        if not videos:
            snippet = self._trim_text(str(payload.get("bodyText") or ""), max_length=180)
            detail = f" 页面摘要：{snippet}" if snippet else ""
            return FavoriteFetchResult(
                success=False,
                favorite_id=normalized_uid,
                title=self._extract_title(payload, normalized_uid),
                owner_name=self._extract_owner_name(payload),
                message=f"投稿网页已打开，但没有从页面内容中提取到视频。{detail}",
                videos=(),
            )

        return FavoriteFetchResult(
            success=True,
            favorite_id=normalized_uid,
            title=self._extract_title(payload, normalized_uid),
            owner_name=self._extract_owner_name(payload),
            message=f"UP 主投稿网页第 {page} 页已抓取，提取到 {len(videos)} 条视频。",
            videos=videos,
        )

    def _load_and_collect(
        self,
        *,
        url: str,
        script: str,
        is_complete: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        """加载网页并轮询 DOM，直到视频卡片出现或超时。"""

        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PySide6.QtNetwork import QNetworkCookie
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        profile = QWebEngineProfile()
        profile.setHttpUserAgent(self.user_agent)
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self._apply_cookies(profile, QNetworkCookie, QUrl)

        page = QWebEnginePage(profile, None)
        loop = QEventLoop()
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)

        state: dict[str, Any] = {
            "attempts": 0,
            "timed_out": False,
            "load_failed": False,
            "payload": {},
        }

        def finish() -> None:
            if loop.isRunning():
                loop.quit()

        def handle_timeout() -> None:
            state["timed_out"] = True
            finish()

        def handle_result(result: Any) -> None:
            payload = self._decode_payload(result)
            state["payload"] = payload
            if is_complete(payload):
                finish()
                return
            if state["attempts"] >= self.poll_attempts:
                finish()
                return
            QTimer.singleShot(self.poll_interval_ms, poll_once)

        def poll_once() -> None:
            if state["timed_out"] or state["load_failed"]:
                finish()
                return
            state["attempts"] += 1
            page.runJavaScript(script, handle_result)

        def handle_load_finished(success: bool) -> None:
            if not success:
                state["load_failed"] = True
                finish()
                return
            poll_once()

        timeout_timer.timeout.connect(handle_timeout)
        page.loadFinished.connect(handle_load_finished)
        timeout_timer.start(self.load_timeout_ms)
        page.setUrl(QUrl(url))
        loop.exec()

        timeout_timer.stop()
        page.deleteLater()
        profile.deleteLater()

        if state["timed_out"]:
            raise RuntimeError(f"页面加载超时：{url}")
        if state["load_failed"]:
            raise RuntimeError(f"页面加载失败：{url}")
        return state["payload"]

    def _apply_cookies(self, profile: Any, cookie_class: Any, url_class: Any) -> None:
        """把本地保存的登录 Cookie 注入临时 WebEngine profile。"""

        cookie_store = profile.cookieStore()
        for name, value in sorted(self.cookies.items()):
            if not value:
                continue
            cookie = cookie_class(str(name).encode("utf-8"), str(value).encode("utf-8"))
            cookie.setDomain(".bilibili.com")
            cookie.setPath("/")
            cookie_store.setCookie(cookie, url_class("https://www.bilibili.com/"))

    @staticmethod
    def _build_video_page_script(*, limit: int, target_page: int) -> str:
        """从渲染后的投稿页面切换到目标页，并抽取视频链接、标题和卡片上下文。"""

        return f"""
(() => {{
  const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const isStatsText = (value) => {{
    const text = normalize(value).replace(/^(最新|合作|置顶|推荐)/, "");
    if (!text) return true;
    if (/^\\d+(?:\\.\\d+)?\\s*(?:万|w)?\\s*\\d*(?:\\.\\d+)?\\s*(?:万|w)?\\s*\\d{{1,2}}:\\d{{2}}(?::\\d{{2}})?$/i.test(text)) return true;
    if (/^\\d+(?:\\.\\d+)?\\s*(?:万|w)?(?:播放|弹幕|评论|点赞|收藏)?$/i.test(text)) return true;
    if (/^\\d{{1,2}}:\\d{{2}}(?::\\d{{2}})?$/.test(text)) return true;
    return false;
  }};
  const titleScore = (value) => {{
    const text = normalize(value);
    if (!text || isStatsText(text)) return -100;
    let score = Math.min(text.length, 80);
    if (/[\\u4e00-\\u9fa5A-Za-z]/.test(text)) score += 30;
    if (/播放|弹幕|评论|点赞|收藏|粉丝数|关注数|视频\\s*\\d+/.test(text)) score -= 50;
    if (/^(最新|合作|置顶|推荐)?\\d/.test(text)) score -= 70;
    if (/^BV[0-9A-Za-z]{{10}}$/.test(text)) score -= 80;
    return score;
  }};
  const datePattern = /(20\\d{{2}}[-/年]\\d{{1,2}}[-/月]\\d{{1,2}}|(?:^|[^\\d.])\\d{{1,2}}[-/]\\d{{1,2}}(?:$|[^\\d.])|刚刚|昨天|前天|\\d+\\s*(?:秒|分钟|小时|天)前)/;
  const classText = (node) => String(node && node.className || "");
  const findVideoCard = (anchor) => {{
    // B 站新版投稿页会把封面、标题、日期拆成多个子块；向上找完整卡片才能拿到发布时间。
    const candidates = [];
    let node = anchor;
    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {{
      const cls = classText(node);
      const text = normalize(node.textContent || "");
      if (!text) continue;
      let score = 0;
      if (/\\bbili-video-card\\b/.test(cls)) score += 100;
      if (/(^|\\s)(video-card|VideoCard|small-item)(\\s|$)/.test(cls)) score += 70;
      if (/video-card|VideoCard|small-item/.test(cls) && !/__/.test(cls)) score += 40;
      if (datePattern.test(text)) score += 80;
      if (/播放|弹幕|稍后再看/.test(text)) score += 10;
      if (/__cover|__title|cover-card/.test(cls)) score -= 35;
      score -= Math.min(text.length / 350, 30);
      candidates.push({{ node, score }});
    }}
    const best = candidates.sort((a, b) => b.score - a.score)[0];
    return best && best.score > 0
      ? best.node
      : anchor.closest('li, article, [class*="card"], [class*="Card"]') || anchor.parentElement;
  }};
  const extractDateText = (card) => {{
    if (!card) return "";
    const nodes = Array.from(card.querySelectorAll('time, [datetime], [class*="time"], [class*="date"], [class*="pub"]'));
    const nodeTexts = nodes.flatMap((node) => [
      node.getAttribute("datetime") || "",
      node.getAttribute("title") || "",
      node.getAttribute("aria-label") || "",
      node.textContent || "",
    ]).map(normalize).filter(Boolean);
    const fromNode = nodeTexts.find((text) => datePattern.test(text));
    if (fromNode) return fromNode;
    const fromCard = normalize(card.textContent || "").match(datePattern);
    return fromCard ? fromCard[0] : "";
  }};
  const targetPage = {target_page};
  const parsePageNumber = (value) => {{
    const matched = String(value || "").match(/\\d+/);
    return matched ? Number(matched[0]) : null;
  }};
  const pageFromUrl = () => {{
    try {{
      return Number(new URL(location.href).searchParams.get("pn") || "1") || 1;
    }} catch (_) {{
      return 1;
    }}
  }};
  const clickableNodes = () => Array.from(document.querySelectorAll("button, a, li, span, div"))
    .filter((node) => {{
      const text = normalize(node.textContent || node.getAttribute("aria-label") || node.title || "");
      if (!text) return false;
      const box = node.getBoundingClientRect ? node.getBoundingClientRect() : {{ width: 0, height: 0 }};
      const looksClickable = node.tagName === "A" || node.tagName === "BUTTON" || node.onclick || node.getAttribute("role") === "button" || node.className;
      return looksClickable && box.width >= 0 && box.height >= 0;
    }});
  const isPagerNode = (node) => {{
    if (!node || !node.closest) return false;
    return Boolean(node.closest('[class*="pagenation"], [class*="pagination"], [class*="pager"], .video-footer'));
  }};
  const pagerNodes = () => clickableNodes().filter(isPagerNode);
  const activePageFromDom = () => {{
    const nodes = pagerNodes();
    const active = nodes.find((node) => {{
      const cls = String(node.className || "").toLowerCase();
      const aria = String(node.getAttribute("aria-current") || "").toLowerCase();
      return cls.includes("active") || cls.includes("current") || cls.includes("selected") || aria === "page";
    }});
    const activeNumber = active ? parsePageNumber(active.textContent) : null;
    return activeNumber || pageFromUrl();
  }};
  const currentPage = activePageFromDom();
  const clickNode = (node) => {{
    node.scrollIntoView({{ block: "center", inline: "center" }});
    node.dispatchEvent(new MouseEvent("mouseover", {{ bubbles: true, cancelable: true }}));
    node.dispatchEvent(new MouseEvent("mousedown", {{ bubbles: true, cancelable: true }}));
    node.dispatchEvent(new MouseEvent("mouseup", {{ bubbles: true, cancelable: true }}));
    node.click();
  }};
  const clickFirstTextNode = (patterns) => {{
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let textNode = null;
    while ((textNode = walker.nextNode())) {{
      const text = normalize(textNode.nodeValue || "");
      if (!patterns.some((pattern) => pattern.test(text))) continue;
      const element = textNode.parentElement;
      if (!element) continue;
      const target = element.closest('a, button, [role="button"], [class*="more"], [class*="More"]') || element;
      clickNode(target);
      return true;
    }}
    return false;
  }};
  const clickTargetPage = () => {{
    const nodes = clickableNodes();
    const pagers = pagerNodes();
    if (!location.href.includes("/video") && !location.href.includes("/upload/video")) {{
      const videoMoreButton = document.querySelector('.video-section .btns button:not(.playall-btn), .video-section button.vui_button:not(.playall-btn)');
      if (videoMoreButton) {{
        clickNode(videoMoreButton);
        return "video-section-more";
      }}
      const clickedMoreText = clickFirstTextNode([
        /\\u67e5\\u770b\\u66f4\\u591a/,
        /\\u64ad\\u653e\\u5168\\u90e8/,
        /\\u5168\\u90e8\\u89c6\\u9891/,
      ]);
      if (clickedMoreText) return "more-text";
    }}
    const moreNode = nodes.find((node) => {{
      const text = normalize(node.textContent || node.getAttribute("aria-label") || node.title || "");
      if (!/查看更多|更多|播放全部|全部视频/.test(text)) return false;
      const around = normalize((node.closest("section, div, main") || node.parentElement || node).textContent || "");
      return around.includes("视频") || around.includes("最新发布") || around.includes("投稿");
    }});
    if (moreNode && !location.href.includes("/video") && !location.href.includes("/upload/video")) {{
      clickNode(moreNode);
      return "more";
    }}
    const direct = pagers.find((node) => parsePageNumber(node.textContent) === targetPage);
    if (direct) {{
      clickNode(direct);
      return "page-number";
    }}
    const next = pagers.find((node) => {{
      const text = normalize(node.textContent || node.getAttribute("aria-label") || node.title || "");
      return /下一页|下页|next|>/i.test(text);
    }});
    if (next && currentPage < targetPage) {{
      clickNode(next);
      return "next";
    }}
    return "";
  }};

  window.scrollTo(0, document.body.scrollHeight);
  if (!window.__bilibiliToolArchivePager) {{
    window.__bilibiliToolArchivePager = {{}};
  }}
  const pagerState = window.__bilibiliToolArchivePager;
  const currentKey = `${{targetPage}}:${{currentPage}}:${{location.href}}`;
  if ((targetPage > 1 && currentPage !== targetPage) || (targetPage > 1 && !location.href.includes("/video") && !location.href.includes("/upload/video"))) {{
    const settleCount = pagerState.settleCount || 0;
    if (pagerState.clickedTargetPage !== targetPage || pagerState.lastClickKey !== currentKey || settleCount >= 2) {{
      const action = clickTargetPage();
      if (action) {{
        pagerState.clickedTargetPage = targetPage;
        pagerState.lastClickKey = currentKey;
        pagerState.settleCount = 0;
        return JSON.stringify({{
          title: document.title || "",
          url: location.href,
          bodyText: normalize(document.body ? document.body.innerText : ""),
          videos: [],
          targetPage,
          currentPage,
          navigationPending: true,
          navigationAction: action,
        }});
      }}
    }}
    pagerState.settleCount = settleCount + 1;
    return JSON.stringify({{
      title: document.title || "",
      url: location.href,
      bodyText: normalize(document.body ? document.body.innerText : ""),
      videos: [],
      targetPage,
      currentPage,
      navigationPending: true,
      navigationAction: pagerState.clickedTargetPage === targetPage ? "settling" : "",
    }});
  }}

  const anchors = Array.from(document.querySelectorAll('a[href*="/video/BV"], a[href*="bilibili.com/video/BV"]'));
  const grouped = new Map();
  for (const anchor of anchors) {{
    const href = anchor.href || anchor.getAttribute("href") || "";
    const matched = href.match(/BV[0-9A-Za-z]{{10}}/);
    if (!matched) continue;
    const bvid = matched[0];
    const card = findVideoCard(anchor);
    const img = card ? card.querySelector("img") : null;
    const sameHrefAnchors = Array.from(document.querySelectorAll(`a[href*="${{bvid}}"]`));
    const titleCandidates = [
      anchor.getAttribute("title"),
      anchor.getAttribute("aria-label"),
      anchor.textContent,
      img ? img.alt : "",
      ...sameHrefAnchors.map((node) => node.getAttribute("title") || ""),
      ...sameHrefAnchors.map((node) => node.textContent || ""),
      ...(card ? Array.from(card.querySelectorAll('[class*="title"], [class*="Title"], h3, [title]')).map((node) => node.getAttribute("title") || node.textContent || "") : []),
    ].map(normalize).filter(Boolean);
    const bestTitle = titleCandidates
      .map((text) => ({{ text, score: titleScore(text) }}))
      .sort((a, b) => b.score - a.score)[0]?.text || bvid;
    const current = grouped.get(bvid);
    const next = {{
      bvid,
      href,
      title: bestTitle,
      titleScore: titleScore(bestTitle),
      contextText: normalize(card ? card.textContent : anchor.parentElement ? anchor.parentElement.textContent : ""),
      coverUrl: img ? (img.currentSrc || img.src || "") : "",
      pubText: extractDateText(card),
    }};
    next.isLatestStart = /^最新/.test(next.contextText) || /最新发布/.test(next.contextText);
    if (!current || next.titleScore > current.titleScore) {{
      next.isLatestStart = next.isLatestStart || Boolean(current && current.isLatestStart);
      grouped.set(bvid, next);
    }} else if (current && next.isLatestStart) {{
      current.isLatestStart = true;
    }}
  }}
  let videos = Array.from(grouped.values());
  const latestIndex = videos.findIndex((item) => item.isLatestStart);
  if (latestIndex >= 0) {{
    videos = videos.slice(latestIndex);
  }}
  videos = videos.slice(0, {limit});
  const nameNode = document.querySelector("h1, .h-name, .nickname, .user-name, .up-name, [class*=nickname]");
  return JSON.stringify({{
    title: document.title || "",
    url: location.href,
    ownerName: normalize(nameNode ? nameNode.textContent : ""),
    bodyText: normalize(document.body ? document.body.innerText : ""),
    targetPage,
    currentPage: activePageFromDom(),
    navigationPending: false,
    navigationAction: "",
    videos,
  }});
}})();
"""

    @staticmethod
    def _payload_ready(payload: dict[str, Any], *, target_page: int) -> bool:
        """已到目标页且有视频，或页面已经明确显示空结果时停止等待。"""

        if payload.get("navigationPending"):
            return False

        current_page = payload.get("currentPage")
        if target_page > 1 and isinstance(current_page, (int, float)) and int(current_page) != target_page:
            return False

        videos = payload.get("videos")
        if isinstance(videos, list) and videos:
            return True

        body_text = str(payload.get("bodyText") or "")
        if target_page == 1 and "代表作" in body_text and "最新发布" not in body_text:
            return False
        empty_flags = ("还没有投稿", "暂无视频", "没有更多", "空空如也", "未找到")
        return any(flag in body_text for flag in empty_flags)

    def _build_videos(self, payload: dict[str, Any], *, uid: str) -> tuple[VideoRecord, ...]:
        """把页面提取结果转换成视频记录。"""

        raw_videos = payload.get("videos")
        if not isinstance(raw_videos, list):
            return ()

        owner_name = self._extract_owner_name(payload)
        videos: list[VideoRecord] = []
        seen: set[str] = set()
        for item in raw_videos:
            if not isinstance(item, dict):
                continue
            bvid = str(item.get("bvid") or "").strip()
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            context_text = str(item.get("contextText") or "")
            title = self._extract_video_title(item, fallback=bvid)
            videos.append(
                VideoRecord(
                    bvid=bvid,
                    title=title,
                    page_count=1,
                    owner_uid=uid,
                    owner_name=owner_name,
                    cover_url=self._normalize_cover_url(str(item.get("coverUrl") or "")) or None,
                    description=self._trim_text(context_text, max_length=500) or None,
                    duration_seconds=self._extract_duration_seconds(context_text),
                    pub_time=self._extract_datetime(str(item.get("pubText") or "")) or self._extract_datetime(context_text),
                    source_url=f"https://www.bilibili.com/video/{bvid}",
                )
            )
        return tuple(videos)

    @staticmethod
    def _extract_video_title(item: dict[str, Any], *, fallback: str) -> str:
        """优先取链接标题，再从卡片文本中尽量切出标题。"""

        raw_title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        if raw_title and raw_title != fallback and not BrowserUserArchiveScraper._looks_like_stats_text(raw_title):
            return raw_title

        context = re.sub(r"\s+", " ", str(item.get("contextText") or "")).strip()
        if not context:
            return fallback
        title = re.split(r"(\d{1,2}:\d{2}|播放|弹幕|评论|点赞|收藏|·)", context, maxsplit=1)[0].strip()
        if title and not BrowserUserArchiveScraper._looks_like_stats_text(title):
            return title
        return fallback

    @staticmethod
    def _looks_like_stats_text(value: str) -> bool:
        """判断文本是否更像播放/弹幕/时长统计，而不是标题。"""

        text = re.sub(r"\s+", "", value).strip()
        text = re.sub(r"^(最新|合作|置顶|推荐)", "", text)
        if not text:
            return True
        if re.fullmatch(r"\d+(?:\.\d+)?(?:万|w)?\d*(?:\.\d+)?(?:万|w)?\d{1,2}:\d{2}(?::\d{2})?", text, flags=re.IGNORECASE):
            return True
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
            return True
        return False

    @staticmethod
    def _extract_title(payload: dict[str, Any], uid: str) -> str:
        """返回页面标题。"""

        raw_title = str(payload.get("title") or "").strip()
        return raw_title or f"UP 主 {uid}"

    @staticmethod
    def _extract_owner_name(payload: dict[str, Any]) -> str | None:
        """从页面标题或页头提取 UP 主名称。"""

        owner_name = re.sub(r"\s+", " ", str(payload.get("ownerName") or "")).strip()
        if owner_name:
            return owner_name

        title = str(payload.get("title") or "")
        title = re.sub(r"的个人空间.*$", "", title).strip()
        return title or None

    @staticmethod
    def _extract_duration_seconds(value: str) -> int | None:
        """从卡片文本中提取 mm:ss 或 hh:mm:ss 时长。"""

        matched = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", value)
        if not matched:
            return None
        parts = matched.group(1).split(":")
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds or None

    @staticmethod
    def _extract_datetime(value: str) -> datetime | None:
        """从 B 站卡片里的完整日期、月日或相对时间中提取发布时间。"""

        text = re.sub(r"\s+", " ", value).strip()
        if not text:
            return None

        now = datetime.now()
        relative = BrowserUserArchiveScraper._extract_relative_datetime(text, now=now)
        if relative is not None:
            return relative

        matched = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?:[ 日T]+(\d{1,2}):(\d{2}))?", text)
        if matched:
            year, month, day = (int(part) for part in matched.groups()[:3])
            hour = int(matched.group(4) or 0)
            minute = int(matched.group(5) or 0)
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                return None

        matched = re.search(r"(?<![\d.])(\d{1,2})[-/](\d{1,2})(?![\d.])(?:[ 日T]+(\d{1,2}):(\d{2}))?", text)
        if matched:
            month = int(matched.group(1))
            day = int(matched.group(2))
            hour = int(matched.group(3) or 0)
            minute = int(matched.group(4) or 0)
            try:
                return datetime(now.year, month, day, hour, minute)
            except ValueError:
                return None

        return None

    @staticmethod
    def _extract_relative_datetime(value: str, *, now: datetime) -> datetime | None:
        """解析“刚刚 / 5小时前 / 昨天”这类 B 站近期发布时间。"""

        text = re.sub(r"\s+", "", value)
        if "刚刚" in text:
            return now.replace(second=0, microsecond=0)
        if "昨天" in text:
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if "前天" in text:
            return (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

        matched = re.search(r"(\d+)(秒|分钟|小时|天)前", text)
        if not matched:
            return None
        amount = int(matched.group(1))
        unit = matched.group(2)
        if unit == "秒":
            delta = timedelta(seconds=amount)
        elif unit == "分钟":
            delta = timedelta(minutes=amount)
        elif unit == "小时":
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(days=amount)
        return (now - delta).replace(second=0, microsecond=0)

    @staticmethod
    def _normalize_cover_url(value: str) -> str:
        """把协议相对图片地址补全。"""

        if value.startswith("//"):
            return f"https:{value}"
        return value

    @staticmethod
    def _decode_payload(result: Any) -> dict[str, Any]:
        """兼容 Qt WebEngine 返回 JSON 字符串或原生字典两种情况。"""

        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            if not result.strip():
                return {}
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                return {"bodyText": result}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _trim_text(value: str, *, max_length: int = 120) -> str:
        """压缩页面文本。"""

        collapsed = re.sub(r"\s+", " ", value).strip()
        if len(collapsed) <= max_length:
            return collapsed
        return f"{collapsed[: max_length - 3]}..."
