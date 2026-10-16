import urllib.parse
import webbrowser
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("CoreAI.WebTools")

def open_url(url: str, new_window: bool = False) -> Dict[str, Any]:
    """
    Opens an arbitrary web URL in the operator's default web browser.
    Ensures URL has a proper scheme (http/https).
    """
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://", "ftp://")):
        clean_url = f"https://{clean_url}"
    
    try:
        if new_window:
            webbrowser.open_new(clean_url)
        else:
            webbrowser.open(clean_url)
        logger.info(f"Opened URL in browser: {clean_url}")
        return {
            "status": "success",
            "url": clean_url,
            "message": f"Successfully opened {clean_url} in your default browser"
        }
    except Exception as e:
        logger.error(f"Failed to open URL {clean_url}: {e}")
        return {
            "status": "error",
            "url": clean_url,
            "error": str(e)
        }

def search_web_query(query: str, engine: str = "duckduckgo") -> Dict[str, Any]:
    """
    Opens a web search query directly in the browser using the specified search engine.
    Supported engines: 'duckduckgo', 'google', 'bing', 'ecosia'.
    """
    clean_query = query.strip()
    encoded = urllib.parse.quote_plus(clean_query)
    
    engine_clean = engine.lower().strip()
    if engine_clean in ("google", "goog"):
        target_url = f"https://www.google.com/search?q={encoded}"
    elif engine_clean in ("bing",):
        target_url = f"https://www.bing.com/search?q={encoded}"
    elif engine_clean in ("ecosia",):
        target_url = f"https://www.ecosia.org/search?q={encoded}"
    else:
        target_url = f"https://duckduckgo.com/?q={encoded}"
        
    return open_url(target_url)

def open_youtube(
    search_query: Optional[str] = None,
    video_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Directly opens YouTube, a search query on YouTube, or a specific YouTube video.
    """
    if video_url:
        return open_url(video_url)
    
    if search_query:
        clean_query = search_query.strip()
        encoded = urllib.parse.quote_plus(clean_query)
        target_url = f"https://www.youtube.com/results?search_query={encoded}"
        res = open_url(target_url)
        if res.get("status") == "success":
            res["message"] = f"Opened YouTube search for '{clean_query}'"
        return res
    
    res = open_url("https://www.youtube.com")
    if res.get("status") == "success":
        res["message"] = "Opened YouTube in default browser"
    return res


# --- JSON Schemas for Tool Catalog ---

open_url_schema = {
    "name": "open_url",
    "description": "Opens a website URL in the host machine's default web browser.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The destination URL (e.g. 'https://github.com', 'wikipedia.org')"
            },
            "new_window": {
                "type": "boolean",
                "description": "Whether to open in a dedicated new browser window"
            }
        },
        "required": ["url"]
    }
}

search_web_query_schema = {
    "name": "search_web_query",
    "description": "Performs a web search by opening search results in the browser (DuckDuckGo, Google, Bing).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query terms or question"
            },
            "engine": {
                "type": "string",
                "description": "Search engine: 'duckduckgo' (default), 'google', 'bing', or 'ecosia'"
            }
        },
        "required": ["query"]
    }
}

open_youtube_schema = {
    "name": "open_youtube",
    "description": "Opens YouTube in the operator's browser, optionally searching for a topic or video query.",
    "parameters": {
        "type": "object",
        "properties": {
            "search_query": {
                "type": "string",
                "description": "Optional search term to find on YouTube (e.g. 'lofi beats', 'quantum computing lecture')"
            },
            "video_url": {
                "type": "string",
                "description": "Optional direct YouTube video or playlist URL"
            }
        }
    }
}


def fetch_url_text(url: str, max_chars: int = 5000, timeout_sec: float = 8.0, **kwargs) -> Dict[str, Any]:
    """Downloads webpage content, strips HTML tags, and extracts clean readable text."""
    import urllib.request
    import re
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"
    try:
        req = urllib.request.Request(
            clean_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CoreAI/0.3"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            html_text = raw.decode(charset, errors="replace")

        # Strip scripts, styles, and tags
        text = re.sub(r'<script.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        truncated = len(text) > max_chars
        preview = text[:max_chars]
        return {
            "status": "success",
            "url": clean_url,
            "text": preview,
            "char_count": len(preview),
            "truncated": truncated
        }
    except Exception as e:
        return {"status": "error", "url": clean_url, "message": f"Failed to fetch webpage text: {e}"}


def http_request_json(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout_sec: float = 10.0,
    **kwargs
) -> Dict[str, Any]:
    """Lightweight REST client for querying or posting JSON to external APIs."""
    import urllib.request
    import json
    clean_method = method.upper().strip()
    clean_url = url.strip()
    req_headers = {"User-Agent": "CoreAI/0.3", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    data_bytes = None
    if json_data is not None:
        data_bytes = json.dumps(json_data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(clean_url, data=data_bytes, headers=req_headers, method=clean_method)
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return {
                "status": "success",
                "http_status": resp.status,
                "url": clean_url,
                "data": parsed
            }
    except Exception as e:
        return {"status": "error", "url": clean_url, "message": f"HTTP request failed: {e}"}


def download_file(
    url: str,
    destination_path: str,
    timeout_sec: float = 30.0,
    **kwargs
) -> Dict[str, Any]:
    """Downloads a file directly from a URL to a local destination."""
    import urllib.request
    import os
    clean_url = url.strip()
    try:
        parent = os.path.dirname(os.path.abspath(destination_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        req = urllib.request.Request(clean_url, headers={"User-Agent": "CoreAI/0.3"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp, open(destination_path, "wb") as out_file:
            while chunk := resp.read(65536):
                out_file.write(chunk)
        size_bytes = os.path.getsize(destination_path)
        return {
            "status": "success",
            "url": clean_url,
            "destination": destination_path,
            "size_bytes": size_bytes,
            "message": f"Successfully downloaded {size_bytes} bytes to '{destination_path}'."
        }
    except Exception as e:
        return {"status": "error", "message": f"Download failed: {e}"}


fetch_url_text_schema = {
    "name": "fetch_url_text",
    "description": "Fetch and extract readable plain text content from a web URL",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Web URL to fetch"},
            "max_chars": {"type": "integer", "default": 5000}
        },
        "required": ["url"]
    }
}

http_request_json_schema = {
    "name": "http_request_json",
    "description": "Send a lightweight HTTP request (GET/POST/PUT/DELETE) and parse JSON response",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "API endpoint URL"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            "json_data": {"type": "object", "description": "JSON payload for POST/PUT"}
        },
        "required": ["url"]
    }
}

download_file_schema = {
    "name": "download_file",
    "description": "Download a remote file or image to a local file path",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Direct file URL to download"},
            "destination_path": {"type": "string", "description": "Target file destination"}
        },
        "required": ["url", "destination_path"]
    }
}

