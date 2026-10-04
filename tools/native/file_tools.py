import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def read_text_file(file_path: str = "", **kwargs) -> Dict[str, Any]:
    """Reads content from a text file."""
    target = file_path or kwargs.get("path") or kwargs.get("filepath") or kwargs.get("filename") or ""
    try:
        if not target or not os.path.exists(target):
            return {"status": "error", "error": f"File not found: {target}"}
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content, "size_bytes": len(content)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def write_text_file(file_path: str = "", content: str = "", **kwargs) -> Dict[str, Any]:
    """Writes content to a text file."""
    target = file_path or kwargs.get("path") or kwargs.get("filepath") or ""
    body = content if content != "" else kwargs.get("text", kwargs.get("data", ""))
    try:
        if not target:
            return {"status": "error", "error": "Missing destination file path"}
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(body)
        return {"status": "success", "file_path": target, "bytes_written": len(body)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def list_dir_contents(directory_path: str = ".", **kwargs) -> Dict[str, Any]:
    """Lists files and folders in a directory."""
    target = kwargs.get("path") or kwargs.get("dir") or kwargs.get("folder") or directory_path or "."
    try:
        if not os.path.exists(target):
            return {"status": "error", "error": f"Directory not found: {target}"}
        items = os.listdir(target)
        return {"status": "success", "items": items, "count": len(items)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

read_file_schema = {
    "name": "read_text_file",
    "description": "Read contents of a text file from disk",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute or relative path to the file"}
        },
        "required": ["file_path"]
    }
}

write_file_schema = {
    "name": "write_text_file",
    "description": "Write text content to a file on disk",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Destination file path"},
            "content": {"type": "string", "description": "Text content to write"}
        },
        "required": ["file_path", "content"]
    }
}

list_dir_schema = {
    "name": "list_dir_contents",
    "description": "List files and directories in a given path",
    "parameters": {
        "type": "object",
        "properties": {
            "directory_path": {"type": "string", "description": "Directory path (defaults to current dir)", "default": "."}
        }
    }
}
