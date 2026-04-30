"""Recovery policy for handling common UI automation failures.

Implements rule-based self-healing for 8 categories of exceptions:
1. Blocking popups (permissions, updates, notifications)
2. Loading delays (spinners, progress bars)
3. Search no results (empty search, typos)
4. Input box not focused (click missed, focus lost)
5. Network errors (timeout, connection lost)
6. Permission popups (camera, microphone, location)
7. Scroll to target (element off-screen)
8. OCR text mismatch (verification failed)
"""

from __future__ import annotations

import logging

from cua_lark.task.schema import Action, Observation, Verdict

logger = logging.getLogger(__name__)


class RecoveryPolicy:
    """Rule-based recovery policy for common UI automation failures."""

    # Category 1: Blocking popups
    POPUP_KEYWORDS = (
        "确定", "取消", "稍后", "更新", "权限", "登录", "弹窗",
        "OK", "Cancel", "Later", "Update", "Permission", "Login",
        "关闭", "Close", "知道了", "Got it", "允许", "Allow", "拒绝", "Deny"
    )

    # Category 2: Loading indicators
    LOADING_KEYWORDS = (
        "loading", "加载中", "正在加载", "请稍候", "处理中",
        "Loading", "Please wait", "Processing", "Waiting"
    )

    # Category 3: Search no results
    NO_RESULT_KEYWORDS = (
        "无结果", "未找到", "没有找到", "无匹配", "搜索结果为空",
        "no results", "no result", "not found", "no matches", "empty"
    )

    # Category 4: Input focus issues
    FOCUS_KEYWORDS = (
        "输入框", "input", "edit", "text box", "请输入", "enter text"
    )

    # Category 5: Network errors
    NETWORK_ERROR_KEYWORDS = (
        "网络错误", "连接失败", "超时", "无法连接", "网络异常",
        "network error", "connection failed", "timeout", "cannot connect",
        "offline", "离线"
    )

    # Category 6: Permission popups (specific)
    PERMISSION_KEYWORDS = (
        "需要权限", "授权", "麦克风", "摄像头", "位置", "通知",
        "permission required", "authorize", "microphone", "camera",
        "location", "notification"
    )

    # Category 7: Scroll indicators
    SCROLL_KEYWORDS = (
        "向下滚动", "向上滚动", "查看更多", "加载更多",
        "scroll down", "scroll up", "see more", "load more"
    )

    def __init__(self, max_retries: int = 2, wait_loading_sec: int = 3) -> None:
        self.max_retries = max_retries
        self.wait_loading_sec = wait_loading_sec
        self.retry_counts: dict[str, int] = {}

    def plan(self, verdict: Verdict, observation: Observation | None = None) -> Action | None:
        """Plan recovery action based on verdict and observation.

        Returns:
            Recovery action if applicable, None if no recovery possible.
        """
        if verdict.status in {"pass", "blocked"}:
            return None

        screen_summary = (observation.screen_summary if observation else "") or ""
        ocr_text = _join_ocr_text(observation)
        visible_text = f"{screen_summary}\n{ocr_text}".lower()

        # Category 6: Permission popups (highest priority, specific handling)
        if _contains_any(visible_text, self.PERMISSION_KEYWORDS):
            logger.info("Detected permission popup, planning allow action")
            return Action(
                type="click",
                target="permission_allow_button",
                metadata={
                    "recovery_rule": "permission_popup",
                    "reason": verdict.reason,
                    "description": "Click allow/授权 button on permission popup",
                },
            )

        # Category 1: Blocking popups (general)
        if _contains_any(visible_text, self.POPUP_KEYWORDS):
            logger.info("Detected blocking popup, planning dismiss action")
            return Action(
                type="press_key",
                target="Escape",
                metadata={
                    "recovery_rule": "dismiss_popup",
                    "reason": verdict.reason,
                    "description": "Press Escape to dismiss popup",
                },
            )

        # Category 2: Loading delays
        if _contains_any(visible_text, self.LOADING_KEYWORDS):
            logger.info(f"Detected loading indicator, planning wait {self.wait_loading_sec}s")
            return Action(
                type="wait",
                target="screen",
                metadata={
                    "recovery_rule": "wait_loading",
                    "seconds": self.wait_loading_sec,
                    "reason": verdict.reason,
                    "description": f"Wait {self.wait_loading_sec}s for loading to complete",
                },
            )

        # Category 5: Network errors
        if _contains_any(visible_text, self.NETWORK_ERROR_KEYWORDS):
            logger.info("Detected network error, planning retry after wait")
            return Action(
                type="wait",
                target="screen",
                metadata={
                    "recovery_rule": "network_error_wait",
                    "seconds": 5,
                    "reason": verdict.reason,
                    "description": "Wait 5s for network recovery, then retry",
                },
            )

        # Category 3: Search no results
        if _contains_any(visible_text, self.NO_RESULT_KEYWORDS):
            logger.info("Detected search no results, planning clear and retype")
            return Action(
                type="clear_and_retype",
                target="search_box",
                metadata={
                    "recovery_rule": "search_no_results",
                    "reason": verdict.reason,
                    "description": "Clear search box and retype query",
                },
            )

        # Category 4: Input box not focused
        if "input" in verdict.reason.lower() or "focus" in verdict.reason.lower():
            logger.info("Detected input focus issue, planning refocus")
            return Action(
                type="click",
                target="message_input",
                metadata={
                    "recovery_rule": "refocus_input",
                    "reason": verdict.reason,
                    "description": "Click input box again to regain focus",
                },
            )

        # Category 7: Scroll to target (if element not visible)
        if "not_found" in verdict.reason.lower() or "not visible" in verdict.reason.lower():
            if observation and observation.accessibility_candidates:
                # Check if target might be off-screen
                logger.info("Target not found, planning scroll down")
                return Action(
                    type="scroll",
                    target="down",
                    metadata={
                        "recovery_rule": "scroll_to_target",
                        "reason": verdict.reason,
                        "description": "Scroll down to find target element",
                        "scroll_amount": 300,
                    },
                )

        # Category 8: OCR text mismatch (verification failed)
        if "ocr" in verdict.reason.lower() or "text_mismatch" in verdict.reason.lower():
            logger.info("Detected OCR mismatch, planning wait and re-verify")
            return Action(
                type="wait",
                target="screen",
                metadata={
                    "recovery_rule": "ocr_mismatch_wait",
                    "seconds": 2,
                    "reason": verdict.reason,
                    "description": "Wait 2s for UI to stabilize, then re-verify",
                },
            )

        # Fallback: Generic retry with limit
        retry_key = _retry_key(verdict, observation)
        current = self.retry_counts.get(retry_key, 0)
        if current < self.max_retries:
            self.retry_counts[retry_key] = current + 1
            logger.info(f"Planning generic retry {current + 1}/{self.max_retries}")
            return Action(
                type="retry",
                target=verdict.evidence.get("target") if verdict.evidence else None,
                metadata={
                    "recovery_rule": "retry_failed_action",
                    "reason": verdict.reason,
                    "retry_count": self.retry_counts[retry_key],
                    "max_retries": self.max_retries,
                    "description": f"Retry failed action (attempt {current + 1}/{self.max_retries})",
                },
            )

        logger.warning(f"No recovery action available for verdict: {verdict.reason}")
        return None

    def reset_retry_counts(self) -> None:
        """Reset retry counters (call after successful step)."""
        self.retry_counts.clear()


def _join_ocr_text(observation: Observation | None) -> str:
    """Extract all OCR text from observation."""
    if observation is None:
        return ""
    return "\n".join(str(item.get("text", "")) for item in observation.ocr_texts if isinstance(item, dict))


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    lowered_keywords = (keyword.lower() for keyword in keywords)
    return any(keyword in text for keyword in lowered_keywords)


def _retry_key(verdict: Verdict, observation: Observation | None) -> str:
    """Generate unique key for retry tracking."""
    step_index = observation.step_index if observation else "unknown"
    return f"{step_index}:{verdict.status}:{verdict.reason}"
