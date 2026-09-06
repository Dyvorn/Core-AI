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
