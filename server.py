# -*- coding: utf-8 -*-
"""A股投资工具箱 · 本地 Web 服务（FastAPI + ECharts）

启动：双击「启动面板.bat」，或运行  python server.py
默认端口 8520（被占用时自动顺延）；可用环境变量 INVEST_PORT 指定端口。
加 --no-browser 参数则不自动打开浏览器。
"""
import os
import socket
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402

import api  # noqa: E402

app = FastAPI(title="A股投资工具箱", docs_url=None, redoc_url=None, openapi_url=None)

ROUTES = {
    "status": api.status, "settings": api.update_settings, "files": api.files, "upload": api.upload,
    "overview": api.overview, "single": api.single, "spmo": api.spmo,
    "rotation": api.rotation, "dual": api.dual, "save_report": api.save_report,
    "dl_tickflow": api.dl_tickflow, "dl_fund": api.dl_fund, "board": api.board, "board_save": api.board_save,
    "index": api.index_panel, "futures": api.futures,
}
USER_ERRORS = (ValueError, RuntimeError, FileNotFoundError, KeyError, TypeError)


async def _params(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        data = {}
    return data if isinstance(data, dict) else {}


def _err(e: Exception, code: int = 400) -> JSONResponse:
    return JSONResponse({"error": str(e) or e.__class__.__name__}, status_code=code)


@app.post("/api/export/{name}")
async def export(name: str, request: Request):
    params = await _params(request)
    kind = params.pop("_kind", "xlsx")
    filename = params.pop("_filename", f"{name}.xlsx")
    try:
        data = await run_in_threadpool(api.export_xlsx, name, kind, params)
    except USER_ERRORS as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return _err(e, 500)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@app.post("/api/{name}")
async def call(name: str, request: Request):
    fn = ROUTES.get(name)
    if fn is None:
        return _err(KeyError(f"未知接口：{name}"), 404)
    params = {k: v for k, v in (await _params(request)).items() if not k.startswith("_")}
    try:
        result = await run_in_threadpool(lambda: fn(**params))
        return JSONResponse(api.J(result))
    except USER_ERRORS as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return _err(e, 500)


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


app.mount("/", StaticFiles(directory=str(ROOT / "static"), html=True), name="static")


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(start: int) -> int:
    for p in range(start, start + 30):
        if _port_free(p):
            return p
    raise SystemExit(f"端口 {start}~{start + 29} 都被占用，请用环境变量 INVEST_PORT 指定其他端口")


if __name__ == "__main__":
    import uvicorn

    want = int(os.environ.get("INVEST_PORT", "8520"))
    port = pick_port(want)
    url = f"http://127.0.0.1:{port}"
    print("=" * 52)
    print("  A股投资工具箱 已启动")
    if port != want:
        print(f"  端口 {want} 已被占用，自动改用 {port}")
    print(f"  浏览器访问：{url}")
    print("  关闭本窗口即可退出")
    print("=" * 52)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
