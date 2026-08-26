"""week15 习题测试（hermetic，≥5 例 + 覆盖全部纯函数）。"""

from __future__ import annotations

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "week15_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

is_valid_magic = _mod.is_valid_magic  # type: ignore[attr-defined]
check_content_length = _mod.check_content_length  # type: ignore[attr-defined]
InMemoryRateLimiter = _mod.InMemoryRateLimiter  # type: ignore[attr-defined]
cors_origins_from_env = _mod.cors_origins_from_env  # type: ignore[attr-defined]
is_origin_allowed = _mod.is_origin_allowed  # type: ignore[attr-defined]
escape_html = _mod.escape_html  # type: ignore[attr-defined]


# ------------------------------------------------------------------
# 1. 魔数校验
# ------------------------------------------------------------------
def test_is_valid_magic_wav_true():
    assert is_valid_magic(".wav", b"RIFFxxxx") is True
    assert is_valid_magic(".WAV", b"RIFF\x00\x00") is True  # 大小写


def test_is_valid_magic_rejects_fake_wav():
    assert is_valid_magic(".wav", b"hello world") is False
    assert is_valid_magic(".wav", b"BAD!") is False


def test_is_valid_magic_empty_header():
    assert is_valid_magic(".wav", b"") is True  # 由空文件分支处理


def test_is_valid_magic_mp3():
    assert is_valid_magic(".mp3", b"ID3\x03\x00") is True
    assert is_valid_magic(".mp3", b"\xff\xfb\x90\x00") is True  # frame sync
    assert is_valid_magic(".mp3", b"hello") is False


def test_is_valid_magic_flac_ogg_m4a_webm():
    assert is_valid_magic(".flac", b"fLaC\x00") is True
    assert is_valid_magic(".ogg", b"OggS\x00") is True
    assert is_valid_magic(".m4a", b"\x00\x00\x00\x18ftypmp42") is True
    assert is_valid_magic(".webm", b"\x1aE\xdf\xa3\x00") is True
    assert is_valid_magic(".flac", b"BAD!") is False


# ------------------------------------------------------------------
# 2. Content-Length 预检
# ------------------------------------------------------------------
def test_check_content_length_under_limit():
    assert check_content_length("1024", 500 * 1024 * 1024) == (True, None)
    assert check_content_length("0", 100) == (True, None)


def test_check_content_length_over_limit():
    ok, msg = check_content_length(str(600 * 1024 * 1024), 500 * 1024 * 1024)
    assert ok is False
    assert msg is not None and "500MB" in msg


def test_check_content_length_none_and_invalid():
    assert check_content_length(None, 100) == (True, None)
    assert check_content_length("not-a-number", 100) == (True, None)
    assert check_content_length("", 100) == (True, None)


# ------------------------------------------------------------------
# 3. 限流计数
# ------------------------------------------------------------------
def test_ratelimit_within_limit():
    limiter = InMemoryRateLimiter(rpm=3, window_seconds=60, _now=lambda: 0)
    assert limiter.is_allowed("ip1") == (True, 0)
    assert limiter.is_allowed("ip1") == (True, 0)
    assert limiter.is_allowed("ip1") == (True, 0)


def test_ratelimit_exceeded_returns_retry():
    limiter = InMemoryRateLimiter(rpm=2, window_seconds=60, _now=lambda: 0)
    assert limiter.is_allowed("k")[0] is True
    assert limiter.is_allowed("k")[0] is True
    ok, retry = limiter.is_allowed("k")
    assert ok is False
    assert retry >= 1


def test_ratelimit_window_rollover():
    clock = [0.0]
    limiter = InMemoryRateLimiter(rpm=1, window_seconds=60, _now=lambda: clock[0])
    assert limiter.is_allowed("x")[0] is True
    assert limiter.is_allowed("x")[0] is False
    clock[0] = 61
    assert limiter.is_allowed("x")[0] is True


def test_ratelimit_ip_isolation_and_reset():
    limiter = InMemoryRateLimiter(rpm=1, window_seconds=60, _now=lambda: 0)
    assert limiter.is_allowed("a")[0] is True
    assert limiter.is_allowed("a")[0] is False
    # 不同 IP 不受影响
    assert limiter.is_allowed("b")[0] is True
    limiter.reset()
    assert limiter.store_size == 0
    assert limiter.is_allowed("a")[0] is True


# ------------------------------------------------------------------
# 4. CORS 源判定
# ------------------------------------------------------------------
def test_cors_allowlist_default():
    assert cors_origins_from_env("") == [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost",
    ]
    assert cors_origins_from_env("   ") == [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost",
    ]


def test_cors_allowlist_parse():
    assert cors_origins_from_env("http://a.com, http://b.com ") == [
        "http://a.com",
        "http://b.com",
    ]
    assert cors_origins_from_env("http://a.com,, ,http://b.com") == [
        "http://a.com",
        "http://b.com",
    ]


def test_is_origin_allowed_exact_and_wildcard():
    allowlist = ["http://localhost:5173", "http://localhost"]
    assert is_origin_allowed("http://localhost:5173", allowlist) is True
    assert is_origin_allowed("http://localhost", allowlist) is True
    assert is_origin_allowed("http://evil.com", allowlist) is False
    assert is_origin_allowed("http://evil.com", ["*"]) is True
    # 删 origin 后阻断（对应改动并预测实验 3）
    trimmed = [x for x in allowlist if x != "http://localhost"]
    assert is_origin_allowed("http://localhost", trimmed) is False


# ------------------------------------------------------------------
# 5. XSS 转义
# ------------------------------------------------------------------
def test_escape_html_basic():
    assert escape_html("hello") == "hello"
    assert escape_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert escape_html("a & b") == "a &amp; b"


def test_escape_html_quotes():
    assert escape_html('say "hi"') == "say &quot;hi&quot;"
    assert escape_html("it's") == "it&#x27;s"
    assert escape_html("<img onerror=alert(1) src=x>") == "&lt;img onerror=alert(1) src=x&gt;"
