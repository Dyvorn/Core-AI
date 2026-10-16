import os
import subprocess
import logging
from typing import Optional, Dict, Any, List
from core.state import StateManager

logger = logging.getLogger(__name__)

_state_manager: Optional[StateManager] = None

def set_state_manager(sm: StateManager):
    global _state_manager
    _state_manager = sm

def _get_sm() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def get_git_status(repo_path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Checks git branch, staged/unstaged changes, and untracked files in the current repository.
    Provides instant visibility into project state.
    """
    target_dir = repo_path or os.getcwd()
    try:
        # Check current branch
        branch_proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=3.0
        )
        branch = branch_proc.stdout.strip() or "detached"

        # Check status short
        status_proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=5.0
        )
        lines = [line.strip() for line in status_proc.stdout.splitlines() if line.strip()]
        
        modified = [l for l in lines if l.startswith("M") or " M " in l]
        untracked = [l for l in lines if l.startswith("??")]
        deleted = [l for l in lines if l.startswith("D") or " D " in l]

        is_clean = len(lines) == 0

        # Recent commit
        commit_proc = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=3.0
        )
        last_commit = commit_proc.stdout.strip()

        return {
            "status": "success",
            "branch": branch,
            "is_clean": is_clean,
            "total_changes": len(lines),
            "modified_count": len(modified),
            "untracked_count": len(untracked),
            "deleted_count": len(deleted),
            "last_commit": last_commit,
            "summary": "Working tree clean." if is_clean else f"{len(lines)} file(s) modified/untracked on branch '{branch}'."
        }
    except Exception as e:
        return {"status": "error", "message": f"Git command failed: {e}"}


def manage_notes(
    action: str = "list",
    title: Optional[str] = None,
    content: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Stores and recalls quick persistent operator scratch notes in SQLite.
    Actions: 'save', 'get', 'list', 'delete'.
    """
    sm = _get_sm()
    act = action.lower().strip()

    if act in ("save", "add", "set"):
        if not title:
            return {"status": "error", "message": "Note title is required to save a note."}
        note_content = content or title
        sm.set_kv(f"note:{title.lower().strip()}", {"title": title, "content": note_content})
        return {"status": "success", "message": f"Note '{title}' saved."}

    elif act in ("get", "read", "show"):
        if not title:
            return {"status": "error", "message": "Note title is required to read a note."}
        data = sm.get_kv(f"note:{title.lower().strip()}")
        if data:
            return {"status": "success", "title": data.get("title", title), "content": data.get("content")}
        return {"status": "error", "message": f"Note '{title}' not found."}

    elif act in ("delete", "remove", "rm"):
        if not title:
            return {"status": "error", "message": "Note title is required to delete a note."}
        ok = sm.delete_kv(f"note:{title.lower().strip()}")
        return {"status": "success" if ok else "error", "message": f"Note '{title}' {'deleted' if ok else 'not found'}."}

    else:
        # Default 'list'
        all_notes = sm.list_kv(prefix="note:")
        items = []
        for k, v in all_notes.items():
            if isinstance(v, dict):
                items.append({"title": v.get("title", k.replace("note:", "")), "content": v.get("content", "")})
            else:
                items.append({"title": k.replace("note:", ""), "content": str(v)})
        return {
            "status": "success",
            "count": len(items),
            "notes": items
        }


# Schemas
get_git_status_schema = {
    "name": "get_git_status",
    "description": "Inspect git branch, modified files, and working tree cleanliness.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Optional directory path (defaults to current project)"}
        }
    }
}

manage_notes_schema = {
    "name": "manage_notes",
    "description": "Save, read, list, or delete persistent operator scratch notes.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["save", "get", "list", "delete"], "default": "list"},
            "title": {"type": "string", "description": "Title of the note"},
            "content": {"type": "string", "description": "Content of the note (for saving)"}
        }
    }
}


def git_diff_summary(
    repo_path: Optional[str] = None,
    staged: bool = False,
    max_lines: int = 60,
    **kwargs
) -> Dict[str, Any]:
    """Inspects pending code changes using git diff."""
    target_dir = repo_path or os.getcwd()
    cmd = ["git", "diff", "--stat"] if not staged else ["git", "diff", "--cached", "--stat"]
    try:
        proc = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True, timeout=5.0)
        stat_output = proc.stdout.strip()
        diff_cmd = ["git", "diff"] if not staged else ["git", "diff", "--cached"]
        proc_diff = subprocess.run(diff_cmd, cwd=target_dir, capture_output=True, text=True, timeout=5.0)
        lines = proc_diff.stdout.splitlines()
        truncated = len(lines) > max_lines
        diff_text = "\n".join(lines[:max_lines])
        if truncated:
            diff_text += f"\n... (truncated {len(lines) - max_lines} additional lines)"
        return {
            "status": "success",
            "stat": stat_output or "No diff",
            "diff_preview": diff_text or "No modifications",
            "is_empty": len(lines) == 0
        }
    except Exception as e:
        return {"status": "error", "message": f"Git diff failed: {e}"}


def git_commit_changes(
    message: str,
    repo_path: Optional[str] = None,
    stage_all: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Commits modified files to git with a commit message."""
    target_dir = repo_path or os.getcwd()
    if not message or not message.strip():
        return {"status": "error", "message": "Commit message is required."}
    try:
        if stage_all:
            subprocess.run(["git", "add", "."], cwd=target_dir, check=True, timeout=5.0)
        proc = subprocess.run(
            ["git", "commit", "-m", message.strip()],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=10.0
        )
        if proc.returncode == 0:
            return {"status": "success", "message": proc.stdout.strip()}
        return {"status": "error", "message": proc.stderr.strip() or proc.stdout.strip()}
    except Exception as e:
        return {"status": "error", "message": f"Git commit failed: {e}"}


def compute_file_hash(file_path: str, algorithm: str = "sha256", **kwargs) -> Dict[str, Any]:
    """Computes cryptographic digest of a file (sha256, md5, sha1)."""
    import hashlib
    clean_alg = algorithm.lower().strip()
    if clean_alg not in ("sha256", "md5", "sha1", "sha512"):
        return {"status": "error", "message": f"Unsupported algorithm '{algorithm}'. Supported: sha256, md5, sha1, sha512"}
    if not os.path.isfile(file_path):
        return {"status": "error", "message": f"File '{file_path}' does not exist or is not a regular file."}
    try:
        hasher = getattr(hashlib, clean_alg)()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        size_bytes = os.path.getsize(file_path)
        return {
            "status": "success",
            "file": os.path.basename(file_path),
            "algorithm": clean_alg,
            "hash": digest,
            "size_bytes": size_bytes
        }
    except Exception as e:
        return {"status": "error", "message": f"Hashing failed: {e}"}


def find_files_by_pattern(
    pattern: str = "*",
    directory: Optional[str] = None,
    recursive: bool = True,
    max_results: int = 50,
    **kwargs
) -> Dict[str, Any]:
    """Finds files matching glob pattern."""
    import glob
    target_dir = directory or kwargs.get("search_dir") or kwargs.get("dir") or kwargs.get("path") or os.getcwd()
    try:
        search_path = os.path.join(target_dir, "**", pattern) if recursive else os.path.join(target_dir, pattern)
        matches = glob.glob(search_path, recursive=recursive)
        results = []
        for m in matches[:max_results]:
            if os.path.isfile(m):
                results.append({
                    "path": m,
                    "relpath": os.path.relpath(m, target_dir),
                    "size_bytes": os.path.getsize(m)
                })
        return {
            "status": "success",
            "count": len(results),
            "total_matched": len(matches),
            "files": results
        }
    except Exception as e:
        return {"status": "error", "message": f"Search failed: {e}"}


def read_json_file(file_path: str, **kwargs) -> Dict[str, Any]:
    """Safely reads and parses a JSON file."""
    import json
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File '{file_path}' not found."}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"status": "success", "file": file_path, "data": data}
    except Exception as e:
        return {"status": "error", "message": f"Failed to parse JSON in '{file_path}': {e}"}


def write_json_file(file_path: str, data: Any, indent: int = 2, **kwargs) -> Dict[str, Any]:
    """Safely serializes and writes data to a formatted JSON file."""
    import json
    try:
        parent = os.path.dirname(os.path.abspath(file_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        return {"status": "success", "file": file_path, "message": f"Successfully wrote JSON to '{file_path}'"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to write JSON: {e}"}


# Schemas
git_diff_schema = {
    "name": "git_diff_summary",
    "description": "Inspect pending staged or unstaged git code changes in the repository",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Optional directory path"},
            "staged": {"type": "boolean", "description": "True to view staged git changes", "default": False}
        }
    }
}

git_commit_schema = {
    "name": "git_commit_changes",
    "description": "Commit modified project files to git with a descriptive message",
    "parameters": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message"},
            "repo_path": {"type": "string", "description": "Optional repository path"},
            "stage_all": {"type": "boolean", "default": True}
        },
        "required": ["message"]
    }
}

file_hash_schema = {
    "name": "compute_file_hash",
    "description": "Calculate cryptographic hash checksum (sha256, md5, sha1) of a file",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file"},
            "algorithm": {"type": "string", "enum": ["sha256", "md5", "sha1", "sha512"], "default": "sha256"}
        },
        "required": ["file_path"]
    }
}

find_files_schema = {
    "name": "find_files_by_pattern",
    "description": "Search workspace for files matching glob pattern (e.g. '*.py', '*.md')",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py')"},
            "directory": {"type": "string", "description": "Optional root directory"},
            "recursive": {"type": "boolean", "default": True}
        },
        "required": ["pattern"]
    }
}

read_json_schema = {
    "name": "read_json_file",
    "description": "Read and parse a JSON structured file",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to JSON file"}
        },
        "required": ["file_path"]
    }
}

write_json_schema = {
    "name": "write_json_file",
    "description": "Write and format structured JSON data to a file",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Destination path"},
            "data": {"description": "Data dictionary or list to write"}
        },
        "required": ["file_path", "data"]
    }
}

