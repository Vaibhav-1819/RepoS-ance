"""
FastAPI Application for RepoSéance.
Provides endpoints for repository import, code scanning, Ollama integration,
project autopsy generation, Ghost Chat with evidence citations, and roadmap management.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .scanner.repo_scanner import scan_repository, safe_extract_zip
from .indexer.vector_store import LocalVectorStore
from .ai.ollama_client import OllamaClient, DEFAULT_OLLAMA_URL, DEFAULT_MODEL
from .ai.autopsy_engine import generate_project_autopsy
from .ai.ghost_chat import answer_ghost_question
from .database import (
    init_db,
    save_project,
    get_all_projects,
    get_project,
    get_project_tasks,
    update_task_status,
    generate_markdown_dossier
)

# Initialize application and database
init_db()
app = FastAPI(
    title="RepoSéance API",
    description="Local-First Software Archaeology & Digital Repository Séance",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global runtime state
ollama_client = OllamaClient(DEFAULT_OLLAMA_URL, DEFAULT_MODEL)
vector_stores: Dict[str, LocalVectorStore] = {}
scans_cache: Dict[str, Dict[str, Any]] = {}
UPLOAD_TEMP_DIR = Path("temp_uploads")
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)


# Models
class PathImportRequest(BaseModel):
    path: str


class TaskUpdateRequest(BaseModel):
    status: str


class ChatRequest(BaseModel):
    question: str


class ModelConfigRequest(BaseModel):
    base_url: Optional[str] = None
    model_name: Optional[str] = None


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "RepoSéance Backend",
        "version": "1.0.0",
        "offline_mode": True
    }


@app.get("/api/models/status")
async def model_status():
    """Returns local inference status and available open-weight models."""
    return await ollama_client.check_status()


@app.post("/api/models/configure")
async def configure_model(req: ModelConfigRequest):
    """Configures local model name and Ollama URL."""
    global ollama_client
    if req.base_url:
        ollama_client.base_url = req.base_url.rstrip("/")
    if req.model_name:
        ollama_client.model_name = req.model_name
    return await ollama_client.check_status()


@app.post("/api/projects/import")
async def import_project(
    local_path: Optional[str] = Form(None),
    zip_file: Optional[UploadFile] = File(None)
):
    """Imports a local directory path or uploaded ZIP archive and performs initial autopsy."""
    project_id = str(uuid.uuid4())[:8]

    if zip_file:
        dest_zip = UPLOAD_TEMP_DIR / f"{project_id}_{zip_file.filename}"
        extract_dir = UPLOAD_TEMP_DIR / f"extracted_{project_id}"
        with open(dest_zip, "wb") as f:
            content = await zip_file.read()
            f.write(content)
        try:
            repo_path = safe_extract_zip(dest_zip, extract_dir)
            repo_name = Path(zip_file.filename).stem
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Archive extraction failed: {str(e)}")
    elif local_path:
        repo_path = Path(local_path).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Invalid local directory path: {local_path}")
        repo_name = repo_path.name
    else:
        raise HTTPException(status_code=400, detail="Must provide either local_path or zip_file")

    # 1. Deterministic Scan
    try:
        scan_data = scan_repository(repo_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

    # 2. Build local retrieval index
    vs = LocalVectorStore()
    vs.build_index(repo_path)
    vector_stores[project_id] = vs
    scans_cache[project_id] = scan_data

    # 3. Generate Project Autopsy
    autopsy = await generate_project_autopsy(scan_data, ollama_client)

    # 4. Save to SQLite
    save_project(project_id, repo_name, str(repo_path), scan_data, autopsy)

    return {
        "project_id": project_id,
        "name": repo_name,
        "path": str(repo_path),
        "scan": scan_data,
        "autopsy": autopsy
    }


@app.get("/api/projects")
async def list_projects():
    """Lists all stored projects."""
    return get_all_projects()


@app.get("/api/projects/{project_id}")
async def fetch_project(project_id: str):
    """Retrieves full details of a project."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.get("/api/projects/{project_id}/analysis")
async def fetch_project_analysis(project_id: str):
    """Retrieves the latest autopsy and scan findings for a project."""
    proj = get_project(project_id)
    if not proj or "analysis" not in proj:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return proj["analysis"]


@app.post("/api/projects/{project_id}/chat")
async def chat_with_ghost(project_id: str, req: ChatRequest):
    """Asks questions about the codebase with evidence citations."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    # Re-instantiate vector store if not in memory
    if project_id not in vector_stores:
        source_path = Path(proj["source_path"])
        if source_path.exists():
            vs = LocalVectorStore()
            vs.build_index(source_path)
            vector_stores[project_id] = vs
        else:
            raise HTTPException(status_code=400, detail="Repository path is no longer available on disk.")

    scan_data = scans_cache.get(project_id, proj.get("analysis", {}).get("scan", {}))
    return await answer_ghost_question(req.question, vector_stores[project_id], ollama_client, scan_data)


@app.get("/api/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    """Lists revival tasks for the project."""
    return get_project_tasks(project_id)


@app.patch("/api/projects/{project_id}/tasks/{task_id}")
async def update_task(project_id: str, task_id: str, req: TaskUpdateRequest):
    """Updates a revival task's status ('Pending', 'In Progress', 'Completed')."""
    if req.status not in ["Pending", "In Progress", "Completed", "Dismissed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    success = update_task_status(task_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "updated", "task_id": task_id, "new_status": req.status}


@app.get("/api/projects/{project_id}/report", response_class=PlainTextResponse)
async def export_report(project_id: str):
    """Exports a comprehensive Markdown autopsy dossier."""
    return generate_markdown_dossier(project_id)


# Mount frontend static web app
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

