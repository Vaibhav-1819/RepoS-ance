"""
Git repository history analysis for RepoSéance.
Extracts commit volume, author lists, timeline, and dormancy metrics safely and read-only.
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def analyze_git_history(repo_path: Path) -> Dict[str, Any]:
    """Analyzes local git history using read-only commands. Returns structured metadata."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return {
            "is_git_repo": False,
            "commit_count": 0,
            "first_commit_date": None,
            "last_commit_date": None,
            "dormant_days": 0,
            "authors": [],
            "recent_files": [],
            "status_summary": "Non-Git or unpacked directory"
        }

    try:
        # Check commit count
        count_res = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        commit_count = int(count_res.stdout.strip()) if count_res.returncode == 0 and count_res.stdout.strip().isdigit() else 0

        if commit_count == 0:
            return {
                "is_git_repo": True,
                "commit_count": 0,
                "first_commit_date": None,
                "last_commit_date": None,
                "dormant_days": 0,
                "authors": [],
                "recent_files": [],
                "status_summary": "Empty Git repository"
            }

        # Last commit date (ISO)
        last_date_res = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        last_commit_date = last_date_res.stdout.strip() if last_date_res.returncode == 0 else None

        # First commit date (ISO)
        first_date_res = subprocess.run(
            ["git", "log", "--reverse", "-1", "--format=%cI"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        first_commit_date = first_date_res.stdout.strip() if first_date_res.returncode == 0 else None

        # Top authors
        authors_res = subprocess.run(
            ["git", "shortlog", "-sn", "--no-merges", "-n", "5", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        authors = []
        if authors_res.returncode == 0:
            for line in authors_res.stdout.strip().splitlines():
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    authors.append({"name": parts[1], "commits": int(parts[0])})

        # Calculate dormancy days
        dormant_days = 0
        if last_commit_date:
            try:
                # Handle ISO format with timezone
                clean_date = last_commit_date.split("T")[0]
                last_dt = datetime.strptime(clean_date, "%Y-%m-%d")
                now_dt = datetime.now()
                dormant_days = max(0, (now_dt - last_dt).days)
            except Exception:
                dormant_days = 0

        # Files modified in the last 5 commits
        recent_files_res = subprocess.run(
            ["git", "log", "-n", "5", "--name-only", "--pretty=format:"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        recent_files = []
        if recent_files_res.returncode == 0:
            seen = set()
            for f in recent_files_res.stdout.splitlines():
                f_clean = f.strip()
                if f_clean and f_clean not in seen:
                    seen.add(f_clean)
                    recent_files.append(f_clean)

        return {
            "is_git_repo": True,
            "commit_count": commit_count,
            "first_commit_date": first_commit_date,
            "last_commit_date": last_commit_date,
            "dormant_days": dormant_days,
            "authors": authors,
            "recent_files": recent_files[:10],
            "status_summary": f"Dormant for {dormant_days} days ({commit_count} commits recorded)" if dormant_days > 180 else f"Active repository ({commit_count} commits recorded)"
        }

    except Exception as e:
        return {
            "is_git_repo": True,
            "commit_count": 0,
            "first_commit_date": None,
            "last_commit_date": None,
            "dormant_days": 0,
            "authors": [],
            "recent_files": [],
            "status_summary": f"Git inspection skipped: {str(e)}"
        }
