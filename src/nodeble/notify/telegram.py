# -*- coding: utf-8 -*-
"""
Telegram 通知模块

简单版实现，通过 Telegram Bot API 发送消息。
后续可扩展为支持不同消息类型（订单通知、错误告警、日报等）。
"""
import html
import logging
import re
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# HTML tags that Telegram supports
_SAFE_TAGS = re.compile(
    r"<(/?)("
    r"b|strong|i|em|u|ins|s|strike|del|span|tg-spoiler|"
    r"a|code|pre|blockquote|tg-emoji"
    r")(\s[^>]*)?>",
    re.IGNORECASE,
)


def _sanitize_html(text: str) -> str:
    """Escape HTML entities in text while preserving known-safe Telegram tags."""
    # Replace safe tags with placeholders, escape everything, restore placeholders
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00PH{len(placeholders) - 1}\x00"

    stashed = _SAFE_TAGS.sub(_stash, text)
    escaped = html.escape(stashed, quote=False)

    for i, orig in enumerate(placeholders):
        escaped = escaped.replace(f"\x00PH{i}\x00", orig)

    return escaped


class TelegramNotifier:
    """Telegram 通知器"""

    def __init__(self, bot_token: str = "", chat_id: str = "", enabled: bool = False):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self._api_base = f"https://api.telegram.org/bot{bot_token}"

    @classmethod
    def from_config(cls, config_path: str = "config/tiger.yaml") -> "TelegramNotifier":
        """从配置文件创建通知器"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            tg_cfg = cfg.get("telegram", {})
            return cls(
                bot_token=tg_cfg.get("bot_token", ""),
                chat_id=str(tg_cfg.get("chat_id", "")),
                enabled=tg_cfg.get("enabled", False),
            )
        except FileNotFoundError:
            logger.warning("配置文件不存在，Telegram 通知已禁用")
            return cls(enabled=False)

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """发送消息
        
        Args:
            message: 消息内容
            parse_mode: 解析模式，HTML 或 Markdown
        
        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug(f"Telegram 通知已禁用，跳过: {message[:50]}...")
            return False

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot_token 或 chat_id 未配置")
            return False

        try:
            safe_message = _sanitize_html(message) if parse_mode == "HTML" else message
            resp = requests.post(
                f"{self._api_base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": safe_message,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info(f"Telegram 消息已发送: {message[:50]}...")
                return True
            else:
                logger.error(f"Telegram 发送失败: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram 发送异常: {e}")
            return False

    # ── 预定义消息模板 ──────────────────────────────────

    def notify_order_placed(self, symbol: str, action: str, quantity: int, 
                            price: Optional[float] = None, order_id: Optional[int] = None) -> bool:
        """通知：订单已提交"""
        price_str = f" @ {price}" if price else " (市价)"
        msg = (
            f"📋 <b>订单已提交</b>\n"
            f"{'🟢 买入' if action == 'BUY' else '🔴 卖出'} {symbol} × {quantity}{price_str}\n"
            f"订单ID: <code>{order_id}</code>"
        )
        return self.send(msg)

    def notify_order_filled(self, symbol: str, action: str, quantity: int, 
                            avg_price: float, order_id: Optional[int] = None) -> bool:
        """通知：订单已成交"""
        msg = (
            f"✅ <b>订单已成交</b>\n"
            f"{'🟢 买入' if action == 'BUY' else '🔴 卖出'} {symbol} × {quantity} @ {avg_price}\n"
            f"订单ID: <code>{order_id}</code>"
        )
        return self.send(msg)

    def notify_order_cancelled(self, symbol: str, order_id: Optional[int] = None) -> bool:
        """通知：订单已撤销"""
        msg = f"❎ <b>订单已撤销</b>\n标的: {symbol}\n订单ID: <code>{order_id}</code>"
        return self.send(msg)

    def notify_error(self, error_msg: str) -> bool:
        """通知：错误告警"""
        msg = f"🚨 <b>错误告警</b>\n<pre>{error_msg}</pre>"
        return self.send(msg)

    def notify_daily_summary(self, summary: str) -> bool:
        """通知：每日摘要"""
        msg = f"📊 <b>每日交易摘要</b>\n{summary}"
        return self.send(msg)
