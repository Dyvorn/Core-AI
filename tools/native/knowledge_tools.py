import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any

logger = logging.getLogger(__name__)

def lookup_knowledge(query: str, language: str = "en") -> Dict[str, Any]:
    """
    Looks up factual knowledge, people, concepts, places, and history from Wikipedia.
    """
    clean_query = query.strip()
    if not clean_query:
        return {"status": "error", "message": "Query parameter cannot be empty"}

    lang = "de" if language.lower() in ["de", "german", "deutsch"] else "en"
    try:
        url = (
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            f"{urllib.parse.quote(clean_query)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-Knowledge/1.0 (contact@coreai.local)"})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        title = data.get("title", clean_query)
        extract = data.get("extract", "")
        description = data.get("description", "")

        if not extract:
            return {"status": "not_found", "message": f"No summary found for '{clean_query}'"}

        return {
            "status": "success",
            "topic": title,
            "description": description,
            "summary": extract,
            "source_url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
        }
    except urllib.error.HTTPError as he:
        if he.code == 404:
            return {"status": "not_found", "message": f"No knowledge entry found for '{clean_query}'"}
        return {"status": "error", "message": f"Knowledge lookup HTTP error {he.code}: {str(he)}"}
    except Exception as e:
        logger.error(f"Error looking up knowledge for '{clean_query}': {e}", exc_info=True)
        return {"status": "error", "message": f"Knowledge lookup failed: {str(e)}"}

knowledge_schema = {
    "name": "lookup_knowledge",
    "description": "Looks up concise, factual encyclopedic knowledge, summaries, biographies, concepts, places, and history.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic, person, term, place, or concept to research"
            },
            "language": {
                "type": "string",
                "description": "Language code ('en' or 'de')",
                "default": "en"
            }
        },
        "required": ["query"]
    }
}
