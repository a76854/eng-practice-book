"""Lab07 starter: FastAPI + SSE 最小骨架，打通上传到转写到总结的 mock 链路。

为什么这样分层：后端用 FastAPI 声明上传与流式契约，SSE 用生成器逐块产出
text/event-stream，前端用 EventSource 逐 delta 渲染，二者通过同一 wire 格式对齐。
本地无真实 ASR 与 LLM 时，只读复用 m2t 的归一与脱敏 mock，保证本机可演示。

Run:
  python main.py --help
  python main.py
  python main.py --serve --port 8000
  curl -N http://127.0.0.1:8000/api/summary/stream
  curl http://127.0.0.1:8000/api/health
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import AsyncGenerator, Iterator


def fake_sse_stream(full_text: str, chunk_size: int = 3, delay: float = 0.0) -> Iterator[str]:
    """仿真 LLM 的 SSE 流：按 chunk_size 切分，逐块产出 SSE 行，无网络。"""
    for i in range(0, len(full_text), chunk_size):
        delta = full_text[i : i + chunk_size]
        payload = json.dumps({"delta": delta}, ensure_ascii=False)
        yield f"data: {payload}\n\n"
        if delay:
            time.sleep(delay)
    yield "data: [DONE]\n\n"


def parse_sse(lines: Iterator[str]) -> str:
    """增量解析 SSE：拼出完整文本，忽略 [DONE]，容错空行。"""
    buf: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line == "data: [DONE]":
            continue
        if line.startswith("data:"):
            raw = line[len("data:") :].strip()
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            buf.append(obj.get("delta", ""))
    return "".join(buf)


def demo_transcribe_result() -> list[dict]:
    """返回 mock 转写结果，经 m2t.asr.normalize_result 归一，可在本机演示。"""
    # 形状同 m2t.asr 的 sentence_info，演示归一后的统一段结构
    mock_raw = [
        {
            "sentence_info": [
                {"text": "大家好，今天讨论外部集成", "start": 0, "end": 1200, "spk": 0},
                {"text": "流式响应能降低首字时延", "start": 1200, "end": 2500, "spk": 1},
            ]
        }
    ]
    try:
        from m2t.asr import normalize_result

        return normalize_result(mock_raw)
    except Exception:
        # 回退：直接返回归一后的近似结构，保证无 m2t 时仍可演示
        return [
            {"speaker": "说话人1", "text": "大家好，今天讨论外部集成", "start": 0.0, "end": 1.2},
            {"speaker": "说话人2", "text": "流式响应能降低首字时延", "start": 1.2, "end": 2.5},
        ]


def demo_summary_text() -> str:
    """返回 mock 总结全量，用于 SSE 流式演示。"""
    return "与外部世界的集成是现代后端的必修课，流式让首字时延从秒级降至百毫秒级。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab07-starter",
        description="Lab07 starter: FastAPI + SSE mock chain (transcribe to summary)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="serve host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="serve port (default: 8000)")
    parser.add_argument("--serve", action="store_true", help="start FastAPI server instead of terminal demo")
    parser.add_argument("--chunk-size", type=int, default=3, help="SSE chunk size for demo (default: 3)")
    parser.add_argument("--delay", type=float, default=0.0, help="per-chunk delay in seconds for demo (default: 0)")
    return parser


def run_terminal_demo(chunk_size: int, delay: float) -> int:
    print("[lab07] 前后端联调与流式响应集成 -- 终端 SSE 仿真")
    print(f"[lab07] python: {sys.version.split()[0]} prefix: {Path(sys.prefix).name}")
    print()

    # 转写 mock 演示
    segments = demo_transcribe_result()
    print(f"[transcribe] mock segments: {len(segments)}")
    for seg in segments:
        print(f"  speaker={seg.get('speaker', '')} text={seg.get('text', '')} start={seg.get('start', 0)}")
    print()

    # SSE 流式仿真
    full = demo_summary_text()
    stream = fake_sse_stream(full, chunk_size=chunk_size, delay=delay)
    chunks = list(stream)
    print(f"[sse] wire 首行: {chunks[0].strip() if chunks else ''}")
    print(f"[sse] lines: {len(chunks)} (含 DONE)")
    rebuilt = parse_sse(iter(chunks))
    print(f"[sse] rebuilt: {rebuilt}")
    assert rebuilt == full, "SSE rebuilt mismatch"
    first_delta = json.loads(chunks[0].strip()[len("data:") :].strip())["delta"] if chunks else ""
    print(f"[sse] first delta: {first_delta}")
    print("[sse] 流式校验通过：增量可拼回全量")
    print()

    # 脱敏演示
    try:
        from m2t.llm import map_llm_error

        sensitive = RuntimeError("request to https://api.example.com failed, key=sk-abc123")
        safe = map_llm_error(sensitive)
        print(f"[llm] safe message: {safe}")
        assert "sk-abc123" not in safe
        print("[llm] 脱敏校验通过：响应不含密钥")
    except Exception as exc:
        print(f"[llm] 脱敏模块未可用，跳过验证: {exc}")

    print()
    print("[hint] 启动服务: python main.py --serve --port 8000")
    print("[hint] 浏览器打开 index.html，观察 EventSource 增量渲染")
    print("[hint] curl 验证: curl -N http://127.0.0.1:8000/api/summary/stream")
    return 0


# FastAPI 层：仅在 --serve 时加载，缺依赖时给友好提示
def create_app():  # type: ignore[no-untyped-def]
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI 未安装，请先 pip install -r requirements.txt") from exc

    app = FastAPI(
        title="Lab07 Starter - Streaming Summary",
        description="Lab07 starter: upload to transcribe to streaming summary",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class TranscribeIn(BaseModel):
        filename: str = "sample.wav"
        language: str = "auto"

    @app.get("/api/health")
    def health():  # type: ignore[no-untyped-def]
        return {"status": "ok", "version": app.version}

    @app.post("/api/transcribe")
    def transcribe(payload: TranscribeIn):  # type: ignore[no-untyped-def]
        try:
            segments = demo_transcribe_result()
            return {"filename": payload.filename, "segments": segments}
        except Exception as exc:
            try:
                from m2t.llm import map_llm_error

                safe = map_llm_error(exc)
            except Exception:
                safe = "转写失败，请稍后重试"
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail=safe) from exc

    @app.get("/api/summary/stream")
    async def summary_stream(chunk_size: int = 3) -> StreamingResponse:  # type: ignore[no-untyped-def]
        full = demo_summary_text()

        async def gen() -> AsyncGenerator[str, None]:
            import asyncio

            for i in range(0, len(full), chunk_size):
                delta = full[i : i + chunk_size]
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.05)
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # 静态前端：若 index.html 在同目录，则挂载到 /
    static_file = Path(__file__).parent / "index.html"
    if static_file.exists():
        app.mount("/", StaticFiles(directory=str(static_file.parent), html=True), name="static")

    return app


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        try:
            app = create_app()
        except RuntimeError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        try:
            import uvicorn
        except ImportError:
            print("[error] uvicorn 未安装，请先 pip install -r requirements.txt", file=sys.stderr)
            return 1
        print(f"[lab07] serving on http://{args.host}:{args.port} (CORS open, SSE at /api/summary/stream)")
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return run_terminal_demo(chunk_size=args.chunk_size, delay=args.delay)


if __name__ == "__main__":
    raise SystemExit(main())
