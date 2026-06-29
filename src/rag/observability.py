"""Observabilidad y mantenimiento (issue #6).

Registro liviano en **JSON Lines** de lo que hace el agente, para auditar,
depurar y mejorar. Es la base que el issue #8 (observabilidad en la nube) amplía.

Dos registros:
  - `data/logs/qa.jsonl`        — una línea por pregunta respondida.
  - `data/feedback/feedback.jsonl` — una línea por feedback 👍/👎 del usuario.

Las **preguntas sin respuesta** (`no_answer`) y el **feedback negativo** quedan
marcados en estos archivos: son el insumo para la curaduría de contenido y el
ciclo de mejora continua que pide el issue.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .generation import Answer

# Append a JSONL desde varios requests concurrentes: serializamos la escritura.
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _qa_path() -> Path:
    return config.LOG_DIR / "qa.jsonl"


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
    _append(
        _qa_path(),
        {
            "ts": _now(),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "question": question,
            "category": category,
            "no_answer": answer.no_answer,
            "confidence": answer.confidence,
            "sources": answer.sources,
            "model": answer.model,
            "latency_ms": answer.latency_ms,
        },
    )


def log_feedback(
    *,
    conversation_id: str | None,
    message_id: str | None,
    rating: int,
    comment: str | None = None,
) -> None:
    """Registra el feedback del usuario (rating +1 / -1)."""
    _append(
        _feedback_path(),
        {
            "ts": _now(),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "comment": comment,
        },
    )


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


def metrics() -> dict[str, Any]:
    """Resumen para mantenimiento: volumen, % sin respuesta, feedback, latencia."""
    qa = _read_jsonl(_qa_path())
    fb = _read_jsonl(_feedback_path())

    total = len(qa)
    unanswered = sum(1 for r in qa if r.get("no_answer"))
    latencies = [r["latency_ms"] for r in qa if r.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    positive = sum(1 for r in fb if r.get("rating", 0) > 0)
    negative = sum(1 for r in fb if r.get("rating", 0) < 0)

    return {
        "total_questions": total,
        "unanswered": unanswered,
        "unanswered_rate": round(unanswered / total, 3) if total else 0.0,
        "feedback_positive": positive,
        "feedback_negative": negative,
        "avg_latency_ms": avg_latency,
    }
