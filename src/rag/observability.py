"""Observabilidad y registro de ejecución (issues #6 y #8).

Dos destinos para cada evento:
  - **Archivos JSON Lines** en disco (local / volumen): `data/logs/qa.jsonl`,
    `data/logs/errors.jsonl` y `data/feedback/feedback.jsonl`. Versionables y
    fáciles de inspeccionar.
  - **stdout en JSON** (una línea por evento): en la nube, el stdout del
    contenedor lo captura **OCI Logging**, sin montar volúmenes.

Cada evento registra contexto para auditar/depurar/mejorar: modelo y **versión de
prompt**, **tokens**, **latencia**, `no_answer`, fuentes y errores. Las preguntas
sin respuesta y el feedback negativo son el insumo de la curaduría (issue #6).
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .generation import Answer

# Append a JSONL desde varios requests concurrentes: serializamos la escritura.
_LOCK = threading.Lock()

# Logger a stdout (lo consume OCI Logging en la nube). Una línea JSON por evento.
_logger = logging.getLogger("techie")
if not _logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(event: str, payload: dict[str, Any], *, file: Path | None = None) -> None:
    """Registra un evento: a stdout (JSON) y, opcionalmente, a un archivo JSONL."""
    record = {"ts": _now(), "event": event, "git_sha": config.GIT_SHA, **payload}
    if config.LOG_STDOUT:
        _logger.info(json.dumps(record, ensure_ascii=False))
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _LOCK:
            with file.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


def _qa_path() -> Path:
    return config.LOG_DIR / "qa.jsonl"


def _errors_path() -> Path:
    return config.LOG_DIR / "errors.jsonl"


def _feedback_path() -> Path:
    return config.FEEDBACK_DIR / "feedback.jsonl"


def log_qa(
    question: str,
    answer: Answer,
    *,
    conversation_id: str | None = None,
    message_id: str | None = None,
    category: str | None = None,
) -> None:
    """Registra una pregunta respondida."""
    _emit(
        "qa",
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "question": question,
            "category": category,
            "no_answer": answer.no_answer,
            "confidence": answer.confidence,
            "sources": answer.sources,
            "model": answer.model,
            "prompt_version": answer.prompt_version,
            "tokens": answer.tokens,
            "latency_ms": answer.latency_ms,
        },
        file=_qa_path(),
    )


def log_feedback(
    *,
    conversation_id: str | None,
    message_id: str | None,
    rating: int,
    comment: str | None = None,
) -> None:
    """Registra el feedback del usuario (rating +1 / -1)."""
    _emit(
        "feedback",
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "comment": comment,
        },
        file=_feedback_path(),
    )


def log_error(where: str, exc: Exception, **context: Any) -> None:
    """Registra un error de ejecución."""
    _emit(
        "error",
        {"where": where, "error": f"{type(exc).__name__}: {exc}", **context},
        file=_errors_path(),
    )


def log_request(method: str, path: str, status: int, latency_ms: int) -> None:
    """Registra un request HTTP (solo a stdout, para trazas en la nube)."""
    _emit("request", {"method": method, "path": path, "status": status,
                      "latency_ms": latency_ms})


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    k = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
    return s[k]


def metrics() -> dict[str, Any]:
    """Resumen para el panel: volumen, sin respuesta, feedback, latencia, tokens, errores."""
    qa = _read_jsonl(_qa_path())
    fb = _read_jsonl(_feedback_path())
    errors = _read_jsonl(_errors_path())

    total = len(qa)
    unanswered = sum(1 for r in qa if r.get("no_answer"))
    latencies = [r["latency_ms"] for r in qa if r.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    tokens = sum(r.get("tokens") or 0 for r in qa)
    positive = sum(1 for r in fb if r.get("rating", 0) > 0)
    negative = sum(1 for r in fb if r.get("rating", 0) < 0)

    return {
        "total_questions": total,
        "unanswered": unanswered,
        "unanswered_rate": round(unanswered / total, 3) if total else 0.0,
        "feedback_positive": positive,
        "feedback_negative": negative,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": _percentile(latencies, 95),
        "total_tokens": tokens,
        "errors": len(errors),
    }
