"""week15 习题参考答案（hermetic 纯函数）。

对应 MeetingToText 只读参考：
- backend/app/routers/upload.py 的 _is_valid_magic / Content-Length 预检
- backend/app/middleware/ratelimit.py 的 InMemoryRateLimiter
- backend/app/config.py 的 cors_origins_from_env 逻辑
- XSS 转义（教学原创）
"""

from __future__ import annotations

import html
import threading
import time
from collections.abc import Callable


# ------------------------------------------------------------------
# 1. 魔数校验
# ------------------------------------------------------------------
def is_valid_magic(ext: str, header: bytes) -> bool:
    """按容器签名判定 header 是否匹配 ext。

    空 header 视为 True（由上层空文件分支另行报“空文件”）。
    逻辑对齐 backend/app/routers/upload.py 的 _is_valid_magic。
    """
    if len(header) == 0:
        return True
    ext = ext.lower()
    if ext == ".wav":
        return header.startswith(b"RIFF")
    if ext == ".flac":
        return header.startswith(b"fLaC")
    if ext in (".ogg", ".oga", ".opus"):
        return header.startswith(b"OggS")
    if ext == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
        )
    if ext in (".m4a", ".mp4", ".mov"):
        return len(header) >= 8 and header[4:8] == b"ftyp"
    # fallback：通用音频签名
    if header.startswith(b"RIFF"):
        return True
    if header.startswith(b"fLaC"):
        return True
    if header.startswith(b"OggS"):
        return True
    if header.startswith(b"ID3"):
        return True
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return True
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return True
    if header.startswith(b"\x1aE\xdf\xa3"):
        return True
    return header.startswith(bytes.fromhex("3026B2758E66CF11"))


# ------------------------------------------------------------------
# 2. Content-Length 预检
# ------------------------------------------------------------------
def check_content_length(
    content_length: str | None, max_size: int
) -> tuple[bool, str | None]:
    """预检 Content-Length 头。

    Returns:
        (通过?, 错误信息)。非法/缺失头视为跳过（由写盘阶段兜底）。
    """
    if content_length is None:
        return True, None
    try:
        cl = int(content_length.strip())
    except (ValueError, AttributeError):
        return True, None
    if cl > max_size:
        return False, f"文件超过 {max_size // (1024 * 1024)}MB 限制"
    return True, None


# ------------------------------------------------------------------
# 3. 限流：固定窗口
# ------------------------------------------------------------------
class InMemoryRateLimiter:
    """固定窗口限流（可注入时钟，hermetic 测试友好）。

    对齐 backend/app/middleware/ratelimit.py 的 InMemoryRateLimiter。
    """

    def __init__(
        self,
        rpm: int = 60,
        window_seconds: int = 60,
        _now: Callable[[], float] = time.time,
    ) -> None:
        self.rpm: int = rpm if rpm > 0 else 60
        self.window_seconds: int = window_seconds
        self._now: Callable[[], float] = _now
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, int]] = {}

    def is_allowed(self, key: str) -> tuple[bool, int]:
        now = self._now()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._store[key] = (now, 1)
                return True, 0
            window_start, count = entry
            elapsed = now - window_start
            if elapsed >= self.window_seconds:
                self._store[key] = (now, 1)
                return True, 0
            if count < self.rpm:
                self._store[key] = (window_start, count + 1)
                return True, 0
            retry_after = int(self.window_seconds - elapsed)
            if retry_after <= 0:
                retry_after = 1
            return False, retry_after

    def reset(self) -> None:
        with self._lock:
            self._store.clear()

    @property
    def store_size(self) -> int:
        with self._lock:
            return len(self._store)


# ------------------------------------------------------------------
# 4. CORS 源判定
# ------------------------------------------------------------------
DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost",
]


def cors_origins_from_env(raw: str) -> list[str]:
    """纯函数版：解析 MTT_CORS_ORIGINS 原始值。

    空串/空白 -> 默认三项；否则按逗号分割、trim、去空。
    对齐 backend/app/config.py 的 cors_origins_from_env。
    """
    if raw.strip() == "":
        return list(DEFAULT_CORS_ORIGINS)
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def is_origin_allowed(origin: str, allowlist: list[str]) -> bool:
    """判定 origin 是否在 allowlist 中。'*' 通配任意源。"""
    if "*" in allowlist:
        return True
    return origin in allowlist


# ------------------------------------------------------------------
# 5. XSS 转义
# ------------------------------------------------------------------
def escape_html(s: str) -> str:
    """对 HTML 特殊字符做转义，输出可安全拼进 HTML 模板。"""
    return html.escape(s, quote=True).replace("'", "&#x27;")
