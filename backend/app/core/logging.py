import sys
import json
import time
import logging
import threading
import contextvars
from collections import deque
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)

MAX_BUFFER_LOGS = 1000

_http_durations: deque = deque(maxlen=1000)


def record_http_duration(duration_ms: float):
    _http_durations.append(duration_ms)


def get_http_durations() -> List[float]:
    return list(_http_durations)


SENSITIVE_PATTERNS = ["password", "token", "secret", "api_key", "authorization", "code", "cookie"]


def sanitize_log_message(msg: str) -> str:
    if not isinstance(msg, str):
        msg = str(msg)
    import re
    msg = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_.]+', r'\1********', msg)
    msg = re.sub(r'(["\']?(?:password|token|secret|code)["\']?\s*[:=]\s*["\']?)[^"\'\s,]+', r'\1********', msg, flags=re.IGNORECASE)
    return msg


class LogRecordEntry:
    def __init__(
        self,
        level: str,
        message: str,
        logger_name: str,
        timestamp: float,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        component: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.level = level
        self.message = sanitize_log_message(message)
        self.logger_name = logger_name
        self.timestamp = timestamp
        self.iso_time = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        self.request_id = request_id
        self.user_id = user_id
        self.component = component or logger_name.split(".")[-1]
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.iso_time,
            "level": self.level,
            "logger": self.logger_name,
            "component": self.component,
            "message": self.message,
            "request_id": self.request_id,
            "user_id": self.user_id,
            **self.extra,
        }


class MemoryRingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = MAX_BUFFER_LOGS):
        super().__init__()
        self.capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            req_id = getattr(record, "request_id", None) or request_id_var.get()
            uid = getattr(record, "user_id", None) or user_id_var.get()
            comp = getattr(record, "component", None) or record.name.split(".")[-1]

            entry = LogRecordEntry(
                level=record.levelname,
                message=record.getMessage(),
                logger_name=record.name,
                timestamp=record.created,
                request_id=req_id,
                user_id=uid,
                component=comp,
            )
            with self._lock:
                self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def query(
        self,
        level: Optional[str] = None,
        search: Optional[str] = None,
        request_id: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        target_level = level.upper() if level and level.upper() != "ALL" else None
        search_lower = search.lower().strip() if search else None

        filtered = []
        skipped = 0

        with self._lock:
            for entry in reversed(self._buffer):
                if target_level and entry.level != target_level:
                    continue
                if request_id and entry.request_id != request_id:
                    continue
                if component and entry.component.lower() != component.lower():
                    continue
                if search_lower:
                    if search_lower not in entry.message.lower() and search_lower not in (entry.request_id or "").lower():
                        continue

                if skipped < offset:
                    skipped += 1
                    continue

                filtered.append(entry.to_dict())
                if len(filtered) >= limit:
                    break

        return filtered

    def clear(self):
        with self._lock:
            self._buffer.clear()


log_ring_buffer = MemoryRingBufferHandler(capacity=MAX_BUFFER_LOGS)


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or request_id_var.get()
        uid = getattr(record, "user_id", None) or user_id_var.get()
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
            "request_id": req_id,
            "user_id": uid,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(log_level: str = "INFO", log_format: str = "json"):
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    if not any(isinstance(h, MemoryRingBufferHandler) for h in root_logger.handlers):
        root_logger.addHandler(log_ring_buffer)

    has_stream_handler = any(isinstance(h, logging.StreamHandler) and not isinstance(h, MemoryRingBufferHandler) for h in root_logger.handlers)
    if not has_stream_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        if log_format == "json":
            console_handler.setFormatter(StructuredJsonFormatter())
        else:
            fmt = "%(asctime)s [%(levelname)s] [%(name)s] [%(request_id)s] %(message)s"
            console_handler.setFormatter(logging.Formatter(fmt))
        root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
