"""
FastAPI 后端 — 认知评估平台数据服务
启动: uvicorn server.main:app --host 0.0.0.0 --port 8082
"""
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
import shutil, json, zipfile, io, traceback

# ---- 日志配置 ----
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("cognitive-assessment")
logger.setLevel(logging.INFO)

# 文件日志（10MB 轮转，保留 5 份）
file_handler = RotatingFileHandler(
    LOG_DIR / "server.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(file_handler)

# 控制台日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
))
logger.addHandler(console_handler)


app = FastAPI(title="认知评估平台")


# ---- CORS 跨域 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 全局异常处理 ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"{request.method} {request.url.path} -> 500: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
    )


# ---- 静态资源缓存 ----
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith(("/audio/", "/stimuli/")):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 24h
        elif path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith(("/lib/", "/css/")):
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif path.startswith("/paradigms/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

app.add_middleware(CacheControlMiddleware)


# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "server" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 挂载静态文件（前端）
app.mount("/lib", StaticFiles(directory=str(ROOT / "lib")), name="lib")
app.mount("/css", StaticFiles(directory=str(ROOT / "css")), name="css")
app.mount("/paradigms", StaticFiles(directory=str(ROOT / "paradigms")), name="paradigms")
app.mount("/stimuli", StaticFiles(directory=str(ROOT / "stimuli")), name="stimuli")
app.mount("/audio", StaticFiles(directory=str(ROOT / "audio")), name="audio")

# 调度系统静态资源 (JS/CSS)
app.mount("/dispatch-static", StaticFiles(directory=str(ROOT / "dispatch")), name="dispatch-static")

# 调度系统 router (API + HTML 页面)
from . import dispatch as _dispatch_module
app.include_router(_dispatch_module.router, prefix="/dispatch", tags=["dispatch"])
logger.info("[dispatch] router mounted at /dispatch")

logger.info(f"数据目录: {DATA_DIR}")
logger.info(f"静态资源: {ROOT}")


@app.get("/sw.js")
async def service_worker():
    """Service Worker 必须从根路径提供，且不能长期缓存"""
    resp = FileResponse(str(ROOT / "sw.js"), media_type="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/manifest.json")
async def manifest():
    return FileResponse(str(ROOT / "manifest.json"), media_type="application/manifest+json")


@app.get("/")
async def landing():
    return FileResponse(str(ROOT / "landing.html"))


@app.get("/app")
async def app_page():
    return FileResponse(str(ROOT / "index.html"))


@app.get("/examiner.html")
async def examiner_page():
    """主试登录页"""
    return FileResponse(str(ROOT / "examiner.html"))


def _write_session_meta(sid: str, payload: dict):
    """写/更新 _session.json (只记录首次出现的主试信息,不覆盖)。不存在 examiner 字段时静默跳过。"""
    examiner_name = (payload.get("examiner_name") or "").strip()
    if not examiner_name:
        return
    examiner_id = (payload.get("examiner_id") or "").strip()
    sid_dir = DATA_DIR / sid
    sid_dir.mkdir(parents=True, exist_ok=True)
    meta_path = sid_dir / "_session.json"
    if meta_path.exists():
        return  # 首次保存后不再覆盖,防止同被试多主试时后者覆盖前者
    from datetime import datetime
    meta = {
        "subject_id": sid,
        "examiner_name": examiner_name,
        "examiner_id": examiner_id,
        "start_time": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[SESSION] {sid} examiner={examiner_name} ({examiner_id or 'no-id'})")


@app.post("/api/save")
async def save_data(payload: dict):
    """保存 CSV/JSON 数据"""
    sid = payload.get("subject_id", "unknown")
    paradigm = payload.get("paradigm", "unknown")
    filename = payload.get("filename", "data.csv")
    content = payload.get("content", "")

    out_dir = DATA_DIR / sid / paradigm
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")

    _write_session_meta(sid, payload)
    logger.info(f"[SAVE] {sid}/{paradigm}/{filename} ({len(content)} bytes)")
    return {"status": "ok", "path": str(out_path.relative_to(DATA_DIR))}


@app.post("/api/save-multi")
async def save_multi(request: Request):
    """保存多文件FormData（VPC/Precheck用）。
    FormData字段: subject_id, paradigm, 以及任意数量的文件blob。
    """
    form = await request.form()
    sid = form.get("subject_id", "unknown")
    paradigm = form.get("paradigm", "unknown")
    out_dir = DATA_DIR / sid / paradigm
    out_dir.mkdir(parents=True, exist_ok=True)

    # 主试元数据(从 FormData 抽,如果有)
    _write_session_meta(sid, {
        "examiner_name": form.get("examiner_name", ""),
        "examiner_id": form.get("examiner_id", ""),
    })

    saved = []
    for key, value in form.multi_items():
        if key in ("subject_id", "paradigm", "examiner_name", "examiner_id"):
            continue
        if hasattr(value, "read"):
            content = await value.read()
            fname = getattr(value, "filename", None) or key
            out_path = out_dir / fname
            out_path.write_bytes(content)
            saved.append(fname)
        elif isinstance(value, str) and len(value) > 0:
            out_path = out_dir / key
            out_path.write_text(value, encoding="utf-8")
            saved.append(key)

    logger.info(f"[SAVE-MULTI] {sid}/{paradigm} -> {len(saved)} files: {saved}")
    return {"status": "ok", "saved": saved, "count": len(saved)}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    subject_id: str = Form("unknown"),
    paradigm: str = Form("unknown"),
    examiner_name: str = Form(""),
    examiner_id: str = Form(""),
):
    """保存二进制文件（PNG截图、视频等）到对应范式目录"""
    out_dir = DATA_DIR / subject_id / paradigm
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _write_session_meta(subject_id, {"examiner_name": examiner_name, "examiner_id": examiner_id})
    size = out_path.stat().st_size
    logger.info(f"[UPLOAD] {subject_id}/{paradigm}/{file.filename} ({size} bytes)")
    return {"status": "ok", "path": str(out_path.relative_to(DATA_DIR)), "size": size}


@app.post("/api/video")
async def save_video(
    file: UploadFile = File(...),
    subject_id: str = Form("unknown"),
    examiner_name: str = Form(""),
    examiner_id: str = Form(""),
):
    """保存视频文件（兼容旧接口）"""
    out_dir = DATA_DIR / subject_id / "video"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _write_session_meta(subject_id, {"examiner_name": examiner_name, "examiner_id": examiner_id})
    size = out_path.stat().st_size
    logger.info(f"[VIDEO] {subject_id}/{file.filename} ({size} bytes)")
    return {"status": "ok", "path": str(out_path.relative_to(DATA_DIR)), "size": size}


@app.get("/api/data/{subject_id}")
async def list_data(subject_id: str):
    """列出被试所有数据文件"""
    sid_dir = DATA_DIR / subject_id
    if not sid_dir.exists():
        return {"files": []}
    files = []
    for f in sid_dir.rglob("*"):
        if f.is_file():
            files.append({"path": str(f.relative_to(sid_dir)), "size": f.stat().st_size})
    return {"files": files}


@app.get("/api/download/{subject_id}")
async def download_data(subject_id: str):
    """打包 ZIP 下载被试全部数据。文件名:{主试姓名}_{sid}_{date}.zip"""
    sid_dir = DATA_DIR / subject_id
    if not sid_dir.exists():
        logger.warning(f"[DOWNLOAD] {subject_id} -> 404 (no data)")
        return JSONResponse({"error": "no data"}, status_code=404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sid_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(sid_dir))

    size = buf.tell()
    buf.seek(0)

    # 从 _session.json 读主试姓名拼文件名;读不到就退回原命名
    examiner_name = ""
    meta_path = sid_dir / "_session.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            examiner_name = (meta.get("examiner_name") or "").strip()
        except Exception as e:
            logger.warning(f"[DOWNLOAD] session.json parse failed: {e}")

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    if examiner_name:
        # 替换文件系统不安全字符,保留中文
        safe_name = examiner_name.replace("/", "_").replace("\\", "_").replace(":", "_")
        zip_name = f"{safe_name}_{subject_id}_{date_str}.zip"
    else:
        zip_name = f"{subject_id}_{date_str}.zip"

    logger.info(f"[DOWNLOAD] {subject_id} -> {zip_name} ({size} bytes)")

    from starlette.responses import StreamingResponse
    from urllib.parse import quote
    # RFC 5987: filename* 支持非ASCII中文
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{subject_id}_{date_str}.zip\"; filename*=UTF-8''{quote(zip_name)}"}
    )
