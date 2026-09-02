import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def read_text_file(file_path: str) -> Dict[str, Any]:
    """Reads content from a text file."""
    try:
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"File not found: {file_path}"}
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content, "size_bytes": len(content)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def write_text_file(file_path: str, content: str) -> Dict[str, Any]:
    """Writes content to a text file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "file_path": file_path, "bytes_written": len(content)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def list_dir_contents(directory_path: str = ".") -> Dict[str, Any]:
    """Lists files and folders in a directory."""
    try:
        if not os.path.exists(directory_path):
            return {"status": "error", "error": f"Directory not found: {directory_path}"}
        items = os.listdir(directory_path)
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
