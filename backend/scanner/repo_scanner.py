"""
Deterministic repository scanner for RepoSéance.
Scans source files, language statistics, dependency manifests, TODOs, and READMEs.
"""

import os
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from .masker import mask_secrets, is_sensitive_file, EXCLUDED_DIRECTORIES
from .git_analyzer import analyze_git_history

LANGUAGE_MAP = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell Script",
    ".bash": "Shell Script",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
}

MANIFEST_FILES = {
    "package.json": "Node.js (npm/yarn)",
    "requirements.txt": "Python (pip)",
    "pyproject.toml": "Python (PEP 518/Poetry/Flit)",
    "setup.py": "Python (Setuptools)",
    "Pipfile": "Python (Pipenv)",
    "Cargo.toml": "Rust (Cargo)",
    "go.mod": "Go (Modules)",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java (Gradle)",
    "Gemfile": "Ruby (Bundler)",
    "composer.json": "PHP (Composer)",
    "Dockerfile": "Docker Container",
    "docker-compose.yml": "Docker Compose",
}

TODO_PATTERN = re.compile(r"(?i)\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s\-]+(.*)")


def safe_extract_zip(zip_path: Path, target_dir: Path) -> Path:
    """Safely extracts a ZIP archive, preventing directory traversal attacks."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as archive:
        for member in archive.infolist():
            # Validate path traversal attempts
            extracted_path = target_dir / member.filename
            try:
                extracted_path.resolve().relative_to(target_dir.resolve())
            except ValueError:
                raise ValueError(f"Path traversal attempt detected in archive: {member.filename}")
            
            # Reject symlinks in archives
            if member.is_dir():
                extracted_path.mkdir(parents=True, exist_ok=True)
            else:
                extracted_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(extracted_path, "wb") as target:
                    target.write(source.read())
    return target_dir


def scan_repository(repo_path: Path) -> Dict[str, Any]:
    """Deterministically scans repository files, structure, manifests, and git history."""
    repo_path = repo_path.resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {repo_path}")

    files_list = []
    language_counts: Dict[str, int] = {}
    manifests: List[Dict[str, str]] = []
    readme_content: Optional[str] = None
    readme_path: Optional[str] = None
    todos: List[Dict[str, Any]] = []
    total_bytes = 0

    # Walk directory safely
    for root, dirs, files in os.walk(repo_path):
        # Exclude blacklisted directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRECTORIES and not d.startswith(".")]

        rel_root = Path(root).relative_to(repo_path)

        for f in files:
            if is_sensitive_file(f):
                continue

            file_path = Path(root) / f
            try:
                size = file_path.stat().st_size
            except Exception:
                size = 0

            # Skip massive files (> 2MB) for performance
            if size > 2 * 1024 * 1024:
                continue

            rel_file_path = str(rel_root / f).replace("\\", "/")
            if rel_file_path.startswith("./"):
                rel_file_path = rel_file_path[2:]

            ext = file_path.suffix.lower()
            lang = LANGUAGE_MAP.get(ext, "Unknown")
            if lang != "Unknown":
                language_counts[lang] = language_counts.get(lang, 0) + 1

            # Check manifests
            if f in MANIFEST_FILES:
                manifests.append({
                    "file": rel_file_path,
                    "ecosystem": MANIFEST_FILES[f]
                })

            # Check README
            if f.lower().startswith("readme") and not readme_content:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as rf:
                        raw_readme = rf.read(15000)  # first 15KB
                        readme_content = mask_secrets(raw_readme)
                        readme_path = rel_file_path
                except Exception:
                    pass

            # Scan source code for TODO/FIXME markers
            if ext in {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".rb"}:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as sc:
                        for line_idx, line in enumerate(sc, start=1):
                            match = TODO_PATTERN.search(line)
                            if match:
                                tag = match.group(1).upper()
                                comment_text = match.group(2).strip()[:150]
                                todos.append({
                                    "file": rel_file_path,
                                    "line": line_idx,
                                    "tag": tag,
                                    "text": mask_secrets(comment_text)
                                })
                                if len(todos) >= 100:
                                    break
                except Exception:
                    pass

            files_list.append({
                "path": rel_file_path,
                "size_bytes": size,
                "language": lang
            })
            total_bytes += size

    # Analyze Git history
    git_info = analyze_git_history(repo_path)

    # Sort languages by prevalence
    sorted_languages = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "repo_name": repo_path.name,
        "repo_path": str(repo_path),
        "total_files": len(files_list),
        "total_bytes": total_bytes,
        "languages": sorted_languages,
        "manifests": manifests,
        "readme": {
            "path": readme_path,
            "content": readme_content
        },
        "todos": todos[:50],  # Keep top 50
        "git": git_info,
        "files": files_list[:300]  # First 300 for inspection
    }
