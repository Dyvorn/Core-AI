import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class ColoredConsoleFormatter(logging.Formatter):
    """Formats log records with colors for console output."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN if COLORAMA_AVAILABLE else "",
        logging.INFO: Fore.GREEN if COLORAMA_AVAILABLE else "",
        logging.WARNING: Fore.YELLOW if COLORAMA_AVAILABLE else "",
        logging.ERROR: Fore.RED if COLORAMA_AVAILABLE else "",
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT if COLORAMA_AVAILABLE else "",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if COLORAMA_AVAILABLE else ""
        
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"{color}[{timestamp}] [{record.levelname:<7}] [{record.name}]{reset}"
        
        # Check for contextual tags
        context_str = ""
        if hasattr(record, "pipeline_id") and record.pipeline_id:
            context_str += f" [pipe:{record.pipeline_id[:8]}]"
        if hasattr(record, "step_id") and record.step_id:
            context_str += f" [step:{record.step_id}]"
            
        message = record.getMessage()
        return f"{prefix}{context_str} {message}"


class ContextFilter(logging.Filter):
    """Injects default context fields if not already present on record."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "pipeline_id"):
            record.pipeline_id = None
        if not hasattr(record, "step_id"):
            record.step_id = None
        return True


class JsonlPipelineLogger:
    """Writes structured JSONL audit logs for pipeline and tool actions."""
    
    def __init__(self, log_path: str = "logs/pipelines.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_event(self, event_type: str, data: Dict[str, Any], pipeline_id: Optional[str] = None, step_id: Optional[str] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "pipeline_id": pipeline_id,
            "step_id": step_id,
            "payload": data
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            # Fallback print to prevent logger from crashing application
            print(f"[LoggingError] Failed to write JSONL audit log: {e}", file=sys.stderr)


# Global singleton instance for pipeline JSONL logging
_pipeline_jsonl_logger: Optional[JsonlPipelineLogger] = None

def get_pipeline_logger() -> JsonlPipelineLogger:
    global _pipeline_jsonl_logger
    if _pipeline_jsonl_logger is None:
        _pipeline_jsonl_logger = JsonlPipelineLogger()
    return _pipeline_jsonl_logger


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str = "logs/core_ai.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5
) -> logging.Logger:
    """Configures structured console, rotating file, and pipeline logging."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup is called multiple times
    if getattr(root_logger, "_is_configured", False):
        return logging.getLogger("CoreAI")

    context_filter = ContextFilter()

    # 1. Colored Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredConsoleFormatter())
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] [pipe:%(pipeline_id)s] [step:%(step_id)s] %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)

    # Initialize JSONL logger
    get_pipeline_logger()

    root_logger._is_configured = True
    logger = logging.getLogger("CoreAI")
    logger.info("Structured logging initialized (Console, RotatingFile, JSONL)")
    return logger
