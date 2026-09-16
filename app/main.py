"""FastAPI backend: card layout engine + D100 Bluetooth printing.

Local, single-user tool: state lives in memory (per job) plus files on
disk under data/jobs/<job_id>/. No auth, meant to run on localhost only.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import pdfgen, printer
from app.layout import compute_layout
from app.models import CardSize, LayoutOptions, LayoutResult, PageSize, SourceItem

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
STATIC_DIR = BASE_DIR / "static"

JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="D100 Card Printer")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/files", StaticFiles(directory=JOBS_DIR), name="files")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.dir = JOBS_DIR / job_id
        self.sources_dir = self.dir / "sources"
        self.output_dir = self.dir / "output"
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.items: list[SourceItem] = []
        self.last_layout: Optional[LayoutResult] = None


JOBS: dict[str, Job] = {}


def _get_job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Job non trovato")
    return job


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/jobs")
def create_job():
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = Job(job_id)
    return {"job_id": job_id}


@app.post("/api/jobs/{job_id}/items")
async def upload_items(job_id: str, files: list[UploadFile] = File(...)):
    job = _get_job(job_id)
    for upload in files:
        ext = Path(upload.filename).suffix.lower()
        kind = "pdf" if ext == ".pdf" else "image" if ext in IMAGE_EXTS else None
        if kind is None:
            raise HTTPException(400, f"Formato non supportato: {upload.filename}")
        item_id = uuid.uuid4().hex[:8]
        dest = job.sources_dir / f"{item_id}{ext}"
        content = await upload.read()
        dest.write_bytes(content)
        page_count, w_mm, h_mm = pdfgen.inspect_source(dest, kind)
        item = SourceItem(
            id=item_id,
            filename=upload.filename,
            kind=kind,
            page_count=page_count,
            detected_width_mm=w_mm,
            detected_height_mm=h_mm,
        )
        job.items.append(item)
    return {"items": job.items}


@app.get("/api/jobs/{job_id}/items")
def list_items(job_id: str):
    job = _get_job(job_id)
    return {"items": job.items}


class ItemUpdate(BaseModel):
    copies: Optional[int] = None


@app.patch("/api/jobs/{job_id}/items/{item_id}")
def update_item(job_id: str, item_id: str, update: ItemUpdate):
    job = _get_job(job_id)
    for item in job.items:
        if item.id == item_id:
            if update.copies is not None:
                item.copies = max(1, update.copies)
            return {"item": item}
    raise HTTPException(404, "Item non trovato")


@app.delete("/api/jobs/{job_id}/items/{item_id}")
def delete_item(job_id: str, item_id: str):
    job = _get_job(job_id)
    before = len(job.items)
    job.items = [i for i in job.items if i.id != item_id]
    if len(job.items) == before:
        raise HTTPException(404, "Item non trovato")
    return {"items": job.items}


class LayoutRequest(BaseModel):
    page: PageSize
    card: CardSize
    opts: LayoutOptions = LayoutOptions()


@app.post("/api/jobs/{job_id}/layout")
def build_layout(job_id: str, req: LayoutRequest):
    job = _get_job(job_id)
    if not job.items:
        raise HTTPException(400, "Nessun file caricato")
    try:
        layout = compute_layout(req.page, req.card, req.opts, job.items)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    source_paths = {
        item.id: next(job.sources_dir.glob(f"{item.id}.*")) for item in job.items
    }
    out_pdf = job.output_dir / "output.pdf"
    pdfgen.render_output_pdf(out_pdf, layout, job.items, req.opts, source_paths)
    previews = pdfgen.render_previews(out_pdf, job.output_dir)

    job.last_layout = layout
    return {
        "layout": layout,
        "output_pdf_url": f"/files/{job_id}/output/output.pdf",
        "preview_urls": [f"/files/{job_id}/output/{p.name}" for p in previews],
    }


@app.get("/api/printer/config")
def get_printer_config():
    return printer.PrinterConfig.load().__dict__


class PrinterConfigUpdate(BaseModel):
    cli_path: Optional[str] = None
    printer_name: Optional[str] = None
    printer_model: Optional[str] = None
    cli_args_template: Optional[list[str]] = None


@app.post("/api/printer/config")
def set_printer_config(update: PrinterConfigUpdate):
    config = printer.PrinterConfig.load()
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    config.save()
    return config.__dict__


@app.post("/api/jobs/{job_id}/print")
def print_job(job_id: str):
    job = _get_job(job_id)
    out_pdf = job.output_dir / "output.pdf"
    if not out_pdf.exists():
        raise HTTPException(400, "Genera prima il layout (nessun output.pdf)")
    result = printer.print_file(out_pdf)
    status = 200 if result.get("success") else 502
    return JSONResponse(result, status_code=status)
