"""
API endpoint integration tests for RepoSéance.
"""

from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_models_status():
    res = client.get("/api/models/status")
    assert res.status_code == 200
    assert "is_available" in res.json()


def test_import_and_analysis_workflow():
    sample_path = str(Path(__file__).parent.parent.parent / "sample_abandoned_repo")
    res = client.post("/api/projects/import", data={"local_path": sample_path})
    assert res.status_code == 200
    data = res.json()
    assert "project_id" in data
    assert data["name"] == "sample_abandoned_repo"
    assert "scan" in data
    assert "autopsy" in data

    proj_id = data["project_id"]

    # Test Chat
    chat_res = client.post(f"/api/projects/{proj_id}/chat", json={"question": "What is the audio sample rate?"})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "answer" in chat_data
    assert len(chat_data["evidence"]) > 0

    # Test Tasks
    tasks_res = client.get(f"/api/projects/{proj_id}/tasks")
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assert len(tasks) > 0

    # Test Task Update
    task_id = tasks[0]["id"]
    patch_res = client.patch(f"/api/projects/{proj_id}/tasks/{task_id}", json={"status": "In Progress"})
    assert patch_res.status_code == 200

    # Test Report Export
    report_res = client.get(f"/api/projects/{proj_id}/report")
    assert report_res.status_code == 200
    assert "# RepoSéance Project Autopsy" in report_res.text
