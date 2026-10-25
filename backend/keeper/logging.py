"""Structured JSON logs to `.runtime/logs/keeper.log` (rotated); readable lines on the console. Secrets redacted."""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
from pathlib import Path

_SECRET_NAMES = re.compile(r"(?i)\b([A-Z0-9_]*(KEY|TOKEN|SECRET)[A-Z0-9_]*)\s*=\s*\S+")


class RedactFilter(logging.Filter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for s in self.secrets:
            msg = msg.replace(s, "«REDACTED»")
        msg = _SECRET_NAMES.sub(r"\1=«REDACTED»", msg)
        record.msg, record.args = msg, ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"at": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name,
             "message": record.getMessage()}
        for k in ("request_id", "job_id"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d)


_configured = False


def setup_logging(level: str, runtime_dir: Path, fmt: str, secrets: list[str]) -> None:
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger()
    root.setLevel(level)
    redact = RedactFilter(secrets)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(runtime_dir / "logs" / "keeper.log", maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(JsonFormatter())
    fh.addFilter(redact)
    ch = logging.StreamHandler()
    ch.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    ch.addFilter(redact)
    ch.setLevel(max(logging.getLevelName(level), logging.INFO))
    root.handlers[:] = [fh, ch]
    for noisy in ("httpx", "httpcore", "openai", "uvicorn.access", "sse_starlette"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
