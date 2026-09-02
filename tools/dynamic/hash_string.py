# Auto-generated dynamic tool: hash_string
# Description: Computes cryptographic hash (sha256, md5, sha1) of a given text

from typing import Dict, Any

def hash_string(text, algorithm) -> Dict[str, Any]:
    """Computes cryptographic hash (sha256, md5, sha1) of a given text"""
    try:
        import hashlib
        text_data = str(text).encode('utf-8')
        algo_name = algorithm.lower() if 'algorithm' in locals() and algorithm else 'sha256'
        if algo_name == 'md5':
            h = hashlib.md5(text_data).hexdigest()
        elif algo_name == 'sha1':
            h = hashlib.sha1(text_data).hexdigest()
        else:
            h = hashlib.sha256(text_data).hexdigest()
        return {'status': 'success', 'hash': h, 'algorithm': algo_name}
    except Exception as e:
        return {"status": "error", "error": str(e)}

hash_string_schema = {
    "name": "hash_string",
    "description": "Computes cryptographic hash (sha256, md5, sha1) of a given text",
    "parameters": {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "String to hash"
        },
        "algorithm": {
            "type": "string",
            "description": "Hash algorithm (sha256, md5, sha1)",
            "default": "sha256"
        }
    },
    "required": [
        "text"
    ]
}
}
