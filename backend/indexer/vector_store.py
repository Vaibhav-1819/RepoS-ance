"""
Local code and documentation retrieval index for RepoSéance.
Provides fast semantic and lexical evidence lookup with file and line citations.
"""

import math
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from .chunker import chunk_file_content
from ..scanner.masker import mask_secrets, is_sensitive_file, EXCLUDED_DIRECTORIES


class LocalVectorStore:
    """Manages chunking, indexing, and evidence retrieval for a scanned repository."""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.term_index: Dict[str, List[int]] = {}

    def build_index(self, repo_path: Path):
        """Indexes eligible text files in the repository."""
        self.chunks.clear()
        self.term_index.clear()

        repo_path = repo_path.resolve()
        eligible_extensions = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".rb", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"
        }

        import os
        for root, dirs, files in os.walk(repo_path):
            # Filter excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRECTORIES and not d.startswith(".")]

            for f in files:
                file_path = Path(root) / f
                if is_sensitive_file(f):
                    continue
                if file_path.suffix.lower() not in eligible_extensions:
                    continue
                try:
                    # Limit file size for indexing
                    if file_path.stat().st_size > 500 * 1024:
                        continue
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                        content = mask_secrets(fp.read())
                        rel_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
                        file_chunks = chunk_file_content(rel_path, content)
                        for chunk in file_chunks:
                            chunk_id = len(self.chunks)
                            self.chunks.append(chunk)

                            # Populate inverted index
                            words = set(re.findall(r"\w+", chunk["content"].lower()))
                            for w in words:
                                if len(w) > 2:
                                    if w not in self.term_index:
                                        self.term_index[w] = []
                                    self.term_index[w].append(chunk_id)
                except Exception:
                    continue

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieves top-k evidence chunks matching query terms."""
        query_words = set(re.findall(r"\w+", query.lower()))
        scores: Dict[int, float] = {}

        for w in query_words:
            if w in self.term_index:
                chunk_ids = self.term_index[w]
                idf = math.log((len(self.chunks) + 1) / (len(chunk_ids) + 1)) + 1.0
                for cid in chunk_ids:
                    # Weight by occurrences in chunk content
                    count = self.chunks[cid]["content"].lower().count(w)
                    scores[cid] = scores.get(cid, 0.0) + (count * idf)

        sorted_cids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for cid, score in sorted_cids:
            chunk = self.chunks[cid]
            results.append({
                "file": chunk["file"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk["content"],
                "chunk_type": chunk["chunk_type"],
                "relevance_score": round(score, 3)
            })

        return results
