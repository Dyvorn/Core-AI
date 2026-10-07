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
