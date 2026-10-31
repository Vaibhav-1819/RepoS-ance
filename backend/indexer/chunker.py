"""
Syntax-aware code and documentation chunker for RepoSéance.
Splits files into bounded chunks with precise start_line and end_line coordinates.
"""

from typing import List, Dict, Any
from pathlib import Path


def chunk_file_content(relative_path: str, content: str, max_chunk_lines: int = 50) -> List[Dict[str, Any]]:
    """Splits a file's content into overlapping or bounded blocks with exact line ranges."""
    lines = content.splitlines()
    if not lines:
        return []

    chunks = []
    total_lines = len(lines)

    # For short files (<= 60 lines), keep as a single chunk
    if total_lines <= 60:
        return [{
            "file": relative_path,
            "start_line": 1,
            "end_line": total_lines,
            "content": "\n".join(lines),
            "chunk_type": "full_file"
        }]

    # Chunking by window with small overlap
    step = max(20, max_chunk_lines - 10)
    for i in range(0, total_lines, step):
        start_line = i + 1
        end_line = min(total_lines, i + max_chunk_lines)
        chunk_lines = lines[i:end_line]

        # Identify simple structural hint (e.g., class or def declaration)
        chunk_type = "code_block"
        for line in chunk_lines[:5]:
            trimmed = line.strip()
            if trimmed.startswith("def ") or trimmed.startswith("function ") or trimmed.startswith("func "):
                chunk_type = "function_definition"
                break
            elif trimmed.startswith("class ") or trimmed.startswith("struct ") or trimmed.startswith("interface "):
                chunk_type = "class_definition"
                break
            elif trimmed.startswith("# ") or trimmed.startswith("## "):
                chunk_type = "doc_header"
                break

        chunks.append({
            "file": relative_path,
            "start_line": start_line,
            "end_line": end_line,
            "content": "\n".join(chunk_lines),
            "chunk_type": chunk_type
        })

        if end_line == total_lines:
            break

    return chunks
