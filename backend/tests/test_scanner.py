"""
Unit tests for RepoSéance scanner, masker, and vector retrieval.
"""

from pathlib import Path
from backend.scanner.masker import mask_secrets, is_sensitive_file
from backend.scanner.repo_scanner import scan_repository
from backend.indexer.chunker import chunk_file_content
from backend.indexer.vector_store import LocalVectorStore
from backend.ai.autopsy_engine import generate_heuristic_autopsy


def test_mask_secrets():
    raw = "Here is my secret sk-1234567890abcdef1234567890 and postgresql://admin:secretPass123@db.com:5432/main"
    masked = mask_secrets(raw)
    assert "[REDACTED_AI_KEY]" in masked
    assert "[REDACTED_PWD]" in masked
    assert "secretPass123" not in masked


def test_is_sensitive_file():
    assert is_sensitive_file(".env") is True
    assert is_sensitive_file("id_rsa") is True
    assert is_sensitive_file("server.pem") is True
    assert is_sensitive_file("main.py") is False


def test_chunking():
    sample_code = "\n".join([f"line_{i} = {i}" for i in range(1, 100)])
    chunks = chunk_file_content("test.py", sample_code, max_chunk_lines=40)
    assert len(chunks) > 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["file"] == "test.py"


def test_scan_and_vector_store():
    fixture_path = Path(__file__).parent.parent.parent / "sample_abandoned_repo"
    scan_data = scan_repository(fixture_path)
    assert scan_data["total_files"] >= 4
    assert len(scan_data["todos"]) >= 2

    vs = LocalVectorStore()
    vs.build_index(fixture_path)
    results = vs.search("AudioChunkProcessor", top_k=2)
    assert len(results) > 0
    matched_files = [r["file"] for r in results]
    assert any("processor.py" in f or "cli.py" in f for f in matched_files)


def test_heuristic_autopsy():
    fixture_path = Path(__file__).parent.parent.parent / "sample_abandoned_repo"
    scan_data = scan_repository(fixture_path)
    autopsy = generate_heuristic_autopsy(scan_data)

    assert "project_purpose" in autopsy
    assert len(autopsy["main_entry_points"]) > 0
    assert len(autopsy["verified_facts"]) > 0
    assert len(autopsy["revival_tasks"]) >= 3
