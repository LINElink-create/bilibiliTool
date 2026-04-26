from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote

from bilibili_tool.domain import UserProbeCandidate, UserProbeResult


@dataclass(slots=True)
class BrowserUserSearch:
    """通过 Qt WebEngine 低频访问 B 站页面，并从页面里提取用户信息。"""

    user_agent: str
    max_candidates: int = 8
    min_poll_attempts: int = 5
    poll_attempts: int = 10
    poll_interval_ms: int = 700
    load_timeout_ms: int = 18000
    _profile: Any = field(init=False, default=None, repr=False)

    def search_users(self, keyword: str) -> UserProbeResult:
        """在 B 站用户搜索页中查找候选 UP 主。"""

        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("User keyword cannot be empty.")

        try:
            payload = self._load_and_collect(
                url=f"https://search.bilibili.com/upuser?keyword={quote(normalized_keyword)}",
                script=self._build_search_script(limit=self.max_candidates),
                is_complete=lambda payload: self._search_payload_ready(payload, normalized_keyword),
            )
        except RuntimeError as exc:
            return UserProbeResult(
                success=False,
                input_mode="user_name",
                input_value=normalized_keyword,
                message=f"浏览器搜索失败：{exc}",
                items=(),
                candidates=(),
            )

        candidates = self._build_candidates(payload.get("users"), keyword=normalized_keyword)
        if candidates:
            return UserProbeResult(
                success=True,
                input_mode="user_name",
                input_value=normalized_keyword,
                message=f"浏览器搜索成功，找到 {len(candidates)} 个候选用户。",
                items=self._build_items(candidates),
                candidates=candidates,
            )

        title = str(payload.get("title") or "-")
        snippet = self._trim_text(str(payload.get("bodyText") or ""), max_length=160)
        detail = f" 页面标题：{title}"
        if snippet:
            detail = f"{detail}；页面摘要：{snippet}"
        return UserProbeResult(
            success=False,
            input_mode="user_name",
            input_value=normalized_keyword,
            message=f"浏览器搜索未找到可用用户结果。{detail}",
            items=(),
            candidates=(),
        )

    def inspect_user_homepage(self, uid: str) -> UserProbeResult:
        """直接访问用户主页，确认该 UID 是否可打开。"""

        normalized_uid = uid.strip()
        if not normalized_uid:
            raise ValueError("UID cannot be empty.")

        try:
            payload = self._load_and_collect(
                url=f"https://space.bilibili.com/{normalized_uid}",
                script=self._build_homepage_script(),
                is_complete=self._homepage_payload_ready,
            )
        except RuntimeError as exc:
            return UserProbeResult(
                success=False,
                input_mode="uid",
                input_value=normalized_uid,
                message=f"主页检查失败：{exc}",
                items=(),
                candidates=(),
            )

        homepage_url = str(payload.get("url") or f"https://space.bilibili.com/{normalized_uid}")
        matched_uid = re.search(r"space\.bilibili\.com/(\d+)", homepage_url)
        homepage_uid = matched_uid.group(1) if matched_uid else normalized_uid
        candidate = UserProbeCandidate(
            uid=homepage_uid,
            name=self._extract_homepage_name(payload, fallback_uid=homepage_uid),
            homepage_url=homepage_url,
            sign=self._trim_text(str(payload.get("descriptionText") or "")) or None,
        )
        items = (
            f"name={candidate.name}",
            f"uid={candidate.uid}",
            f"url={candidate.homepage_url}",
        )
        return UserProbeResult(
            success=bool(candidate.uid),
            input_mode="uid",
            input_value=normalized_uid,
            message="主页可访问，已从页面中提取用户信息。",
            items=items,
            candidates=(candidate,),
        )

    def _load_and_collect(
        self,
        *,
        url: str,
        script: str,
        is_complete: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        """加载页面后轮询执行脚本，直到拿到结果或超时。"""

        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])

        page = QWebEnginePage(self._get_profile(), None)
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
            if state["attempts"] >= self.min_poll_attempts and is_complete(payload):
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

        if state["timed_out"]:
            raise RuntimeError(f"页面加载超时：{url}")
        if state["load_failed"]:
            raise RuntimeError(f"页面加载失败：{url}")
        return state["payload"]

    def _get_profile(self):
        """用户名搜索使用隔离 profile，避免复用登录页 Cookie。"""

        if self._profile is not None:
            return self._profile

        from PySide6.QtWebEngineCore import QWebEngineProfile

        profile = QWebEngineProfile()
        profile.setHttpUserAgent(self.user_agent)
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self._profile = profile
        return profile

    @staticmethod
    def _build_search_script(*, limit: int) -> str:
        """搜索页只回传基础文本和主页链接，复杂筛选放到 Python 侧完成。"""

        return f"""
(() => {{
  const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const anchors = Array.from(document.querySelectorAll('a[href*="space.bilibili.com/"]'));
  return JSON.stringify({{
    title: document.title || "",
    url: location.href,
    bodyText: normalize(document.body ? document.body.innerText : ""),
    users: anchors.slice(0, {limit * 8}).map((anchor) => ({{
      text: normalize(anchor.textContent || ""),
      href: anchor.href || "",
      contextText: normalize(anchor.parentElement ? anchor.parentElement.textContent : ""),
    }})),
  }});
}})();
"""

    @staticmethod
    def _build_homepage_script() -> str:
        """主页脚本只回传标题、页头昵称和简介文本。"""

        return """
(() => {
  const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const headerNode = document.querySelector("h1, .h-name, .nickname, .user-name, .up-name");
  const descMeta = document.querySelector('meta[name="description"]');
  const descNode = document.querySelector(".h-sign, .sign, .bio, .desc");
  return JSON.stringify({
    title: document.title || "",
    url: location.href,
    headerText: normalize(headerNode ? headerNode.textContent : ""),
    descriptionText: normalize(descMeta ? descMeta.content : (descNode ? descNode.textContent : "")),
    bodyText: normalize(document.body ? document.body.innerText : ""),
  });
})();
"""

    def _search_payload_ready(self, payload: dict[str, Any], keyword: str) -> bool:
        """搜索页至少要出现匹配候选，或明确出现“无结果”提示，才结束轮询。"""

        candidates = self._build_candidates(payload.get("users"), keyword=keyword)
        if candidates:
            return True

        raw_body = str(payload.get("bodyText") or "")
        normalized_body = self._normalize_keyword(raw_body)
        normalized_title = self._normalize_keyword(str(payload.get("title") or ""))
        normalized_keyword = self._normalize_keyword(keyword)
        if normalized_keyword and normalized_keyword not in normalized_body and normalized_keyword not in normalized_title:
            return False
        return any(flag in raw_body for flag in ("未找到", "没有找到", "无结果", "无相关"))

    @staticmethod
    def _homepage_payload_ready(payload: dict[str, Any]) -> bool:
        """主页只要有标题或页头文字，就说明页面已经基本可用。"""

        return bool(payload.get("title") or payload.get("headerText") or payload.get("bodyText"))

    def _build_candidates(self, raw_users: Any, *, keyword: str | None = None) -> tuple[UserProbeCandidate, ...]:
        """把页面脚本提取的基础链接转成领域对象。"""

        if not isinstance(raw_users, list):
            return ()

        candidates: list[UserProbeCandidate] = []
        seen_uids: set[str] = set()
        for item in raw_users:
            if not isinstance(item, dict):
                continue

            href = str(item.get("href") or "").strip()
            matched = re.search(r"space\.bilibili\.com/(\d+)", href)
            uid = matched.group(1) if matched else ""
            if not uid or uid in seen_uids:
                continue

            seen_uids.add(uid)
            context_text = self._trim_text(str(item.get("contextText") or ""), max_length=240)
            name = self._extract_candidate_name(
                text=str(item.get("text") or ""),
                context_text=context_text,
                fallback=uid,
            )
            candidates.append(
                UserProbeCandidate(
                    uid=uid,
                    name=name,
                    homepage_url=href or f"https://space.bilibili.com/{uid}",
                    fans=self._extract_fans_from_text(context_text),
                    sign=context_text or None,
                )
            )

        if not keyword:
            return tuple(candidates[: self.max_candidates])

        normalized_keyword = self._normalize_keyword(keyword)
        matched_candidates = [
            candidate
            for candidate in candidates
            if normalized_keyword
            and (
                normalized_keyword in self._normalize_keyword(candidate.name)
                or normalized_keyword in self._normalize_keyword(candidate.sign or "")
            )
        ]
        return tuple((matched_candidates or ())[: self.max_candidates])

    @staticmethod
    def _build_items(candidates: tuple[UserProbeCandidate, ...]) -> tuple[str, ...]:
        """给 GUI 生成易读的候选摘要。"""

        items: list[str] = []
        for candidate in candidates[:5]:
            fans_text = candidate.fans if candidate.fans is not None else "-"
            items.append(f"{candidate.name} | uid={candidate.uid} | fans={fans_text}")
        return tuple(items)

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
        """压缩页面文本，避免把过长摘要直接塞进状态栏。"""

        collapsed = re.sub(r"\s+", " ", value).strip()
        if len(collapsed) <= max_length:
            return collapsed
        return f"{collapsed[: max_length - 3]}..."

    @staticmethod
    def _normalize_keyword(value: str) -> str:
        """统一搜索关键字格式，便于做名称匹配。"""

        return re.sub(r"\s+", "", value).strip().lower()

    @staticmethod
    def _extract_candidate_name(*, text: str, context_text: str, fallback: str) -> str:
        """优先使用链接文本，其次从卡片文本里截取可能的用户名。"""

        normalized_text = re.sub(r"\s+", " ", text).strip()
        if normalized_text:
            return re.sub(r"([0-9]+(?:\.[0-9]+)?\s*(?:万|w)?(?:粉丝)?)$", "", normalized_text, flags=re.IGNORECASE).strip() or fallback

        normalized_context = re.sub(r"\s+", " ", context_text).strip()
        if not normalized_context:
            return fallback

        candidate_name = re.split(r"(粉丝|followers|个视频|视频|Lv)", normalized_context, maxsplit=1)[0].strip(" ·|-")
        cleaned_name = re.sub(r"([0-9]+(?:\.[0-9]+)?\s*(?:万|w)?)$", "", candidate_name, flags=re.IGNORECASE).strip()
        return cleaned_name or fallback

    @staticmethod
    def _extract_fans_from_text(value: str) -> int | None:
        """从搜索卡片文本中提取粉丝数。"""

        matched = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(万|w)?\s*粉丝", value, flags=re.IGNORECASE)
        if not matched:
            return None
        base = float(matched.group(1))
        if matched.group(2):
            base *= 10000
        return int(base)

    def _extract_homepage_name(self, payload: dict[str, Any], *, fallback_uid: str) -> str:
        """主页优先取页头昵称，再回退到标题。"""

        header_text = self._trim_text(str(payload.get("headerText") or ""))
        if header_text:
            return header_text

        title = self._trim_text(str(payload.get("title") or ""))
        cleaned_title = re.sub(r"的个人空间.*$", "", title).strip()
        return cleaned_title or fallback_uid
