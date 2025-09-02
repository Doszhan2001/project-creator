# app/main.py
from fastapi import FastAPI, Form, Request, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import tempfile, zipfile, os, shutil

from .parser import parse_architecture

app = FastAPI(title="Project Generator")

# Надёжные пути относительно текущего файла
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# если у тебя есть static/, можно примонтировать
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _safe_target(base: Path, rel: Path) -> Path:
    """Вернёт безопасный абсолютный путь внутри base, или бросит исключение."""
    # запрещаем абсолютные пути и '..' в частях
    if rel.is_absolute() or any(p == ".." for p in rel.parts):
        raise ValueError("Invalid path (absolute or parent references not allowed)")
    candidate = base / rel
    # resolve(strict=False) безопаснее — не требует существования
    cand_res = candidate.resolve(strict=False)
    base_res = base.resolve(strict=False)
    if not str(cand_res).startswith(str(base_res)):
        raise ValueError("Path escapes base directory")
    return candidate


@app.post("/generate")
async def generate(architecture: str = Form(...), background_tasks: BackgroundTasks = None):
    if not architecture or not architecture.strip():
        raise HTTPException(status_code=400, detail="Empty architecture")

    entries = parse_architecture(architecture)

    tmpdir = Path(tempfile.mkdtemp())
    project_dir = tmpdir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        # создаём структуру безопасно
        for e in entries:
            rel = Path(e["path"])
            try:
                target = _safe_target(project_dir, rel)
            except ValueError as ex:
                # чистим и возвращаем ошибку
                shutil.rmtree(tmpdir, ignore_errors=True)
                raise HTTPException(status_code=400, detail=str(ex))

            if e["is_dir"]:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                # можно добавить шаблонное содержимое по имени файла, сейчас пустой файл
                target.write_text("", encoding="utf-8")

        zip_path = tmpdir / "project.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(project_dir):
                for f in files:
                    fp = Path(root) / f
                    zf.write(fp, fp.relative_to(project_dir))

        # запланировать удаление временной папки после отправки ответа
        if background_tasks is not None:
            background_tasks.add_task(shutil.rmtree, tmpdir, True)
        else:
            # на всякий случай — удалим при ошибке/если background не передан
            pass

        return FileResponse(str(zip_path), filename="project.zip", media_type="application/zip")
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
