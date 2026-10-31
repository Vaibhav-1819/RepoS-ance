"""
SQLite database and persistence layer for RepoSéance.
Stores scanned projects, revival task statuses, and conversation history locally.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = Path("repo_seance.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables for projects, tasks, and messages."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        source_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        total_files INTEGER DEFAULT 0,
        commit_count INTEGER DEFAULT 0,
        analysis_json TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revival_tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        citation TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        evidence_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def save_project(project_id: str, name: str, source_path: str, scan_data: Dict[str, Any], autopsy: Dict[str, Any]):
    """Persists a newly imported project and its generated autopsy & revival tasks."""
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    analysis_payload = {
        "scan": scan_data,
        "autopsy": autopsy
    }

    cursor.execute("""
    INSERT OR REPLACE INTO projects (id, name, source_path, created_at, total_files, commit_count, analysis_json)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        name,
        source_path,
        now,
        scan_data.get("total_files", 0),
        scan_data.get("git", {}).get("commit_count", 0),
        json.dumps(analysis_payload)
    ))

    # Clear previous tasks for this project
    cursor.execute("DELETE FROM revival_tasks WHERE project_id = ?", (project_id,))

    # Insert revival tasks
    for idx, t in enumerate(autopsy.get("revival_tasks", [])):
        task_id = f"{project_id}-task-{idx+1}"
        cursor.execute("""
        INSERT INTO revival_tasks (id, project_id, title, category, description, priority, status, citation)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (
            task_id,
            project_id,
            t.get("title", "Revival Task"),
            t.get("category", "General"),
            t.get("description", ""),
            t.get("priority", "MEDIUM"),
            t.get("citation", "")
        ))

    conn.commit()
    conn.close()


def get_all_projects() -> List[Dict[str, Any]]:
    """Returns list of stored projects."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, source_path, created_at, total_files, commit_count FROM projects ORDER BY created_at DESC")
    rows = cursor.fetchall()
    projects = [dict(r) for r in rows]
    conn.close()
    return projects


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Returns detailed project analysis by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    data = dict(row)
    if data.get("analysis_json"):
        data["analysis"] = json.loads(data["analysis_json"])
    conn.close()
    return data


def get_project_tasks(project_id: str) -> List[Dict[str, Any]]:
    """Retrieves revival tasks for a given project."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM revival_tasks WHERE project_id = ? ORDER BY id ASC", (project_id,))
    rows = cursor.fetchall()
    tasks = [dict(r) for r in rows]
    conn.close()
    return tasks


def update_task_status(task_id: str, new_status: str) -> bool:
    """Updates the status of a revival task ('Pending', 'In Progress', 'Completed')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE revival_tasks SET status = ? WHERE id = ?", (new_status, task_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def generate_markdown_dossier(project_id: str) -> str:
    """Generates an exportable Markdown autopsy dossier for a project."""
    proj = get_project(project_id)
    if not proj:
        return "# Error: Project not found"

    analysis = proj.get("analysis", {})
    scan = analysis.get("scan", {})
    autopsy = analysis.get("autopsy", {})
    tasks = get_project_tasks(project_id)

    lines = [
        f"# RepoSéance Project Autopsy: {proj['name']}",
        f"**Source Path:** `{proj['source_path']}`  ",
        f"**Analysis Date:** {proj['created_at']}  ",
        f"**Engine:** {autopsy.get('inference_engine', 'Local Inference')}  ",
        "",
        "---",
        "",
        "## 1. Project Purpose & Overview",
        f"{autopsy.get('project_purpose', 'N/A')}",
        "",
        "### Detected Languages",
    ]

    for lang, count in scan.get("languages", []):
        lines.append(f"- **{lang}**: {count} files")

    lines.extend([
        "",
        "## 2. Architecture & Entry Points",
        f"{autopsy.get('architecture_summary', 'N/A')}",
        "",
        "**Primary Entry Points:**",
    ])
    for ep in autopsy.get("main_entry_points", []):
        lines.append(f"- `{ep}`")

    lines.extend([
        "",
        "## 3. Git Activity & Dormancy",
        f"- **Total Commits:** {scan.get('git', {}).get('commit_count', 0)}",
        f"- **Last Commit:** {scan.get('git', {}).get('last_commit_date', 'Unknown')}",
        f"- **Dormant Duration:** {scan.get('git', {}).get('dormant_days', 0)} days",
        "",
        "## 4. Verified Facts vs. Hypotheses",
        "",
        "### Verified Facts",
    ])
    for vf in autopsy.get("verified_facts", []):
        lines.append(f"- [x] **{vf.get('description')}** *(Citation: `{vf.get('citation')}`)*")

    lines.extend([
        "",
        "### Hypotheses & Inferences",
    ])
    for hp in autopsy.get("hypotheses", []):
        lines.append(f"- [ ] **{hp.get('claim')}** — *{hp.get('reason')}*")

    lines.extend([
        "",
        "## 5. Revival Roadmap",
        "",
        "| Status | Priority | Category | Task | Citation |",
        "|---|---|---|---|---|",
    ])
    for t in tasks:
        lines.append(f"| {t['status']} | {t['priority']} | {t['category']} | {t['title']} | `{t['citation']}` |")

    lines.extend([
        "",
        "---",
        "*Generated locally by RepoSéance — 100% Offline AI Software Archaeology.*"
    ])

    return "\n".join(lines)
