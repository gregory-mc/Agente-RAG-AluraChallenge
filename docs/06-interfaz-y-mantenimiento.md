# Issue #6 — Implantación, interfaz y mantenimiento

Una **interfaz web de chat** accesible que deja claro que es una IA, muestra las
fuentes, tiene botón de feedback e historial; más la base de **mantenimiento**
(logging, métricas y ciclo de actualización de documentos).

---

## 1. Arquitectura

```
navegador (HTML/CSS/JS estático)
        │  fetch /api/ask
        ▼
FastAPI (rag/web/app.py) ──> RagAgent.answer() ──> recuperación + generación
        │                                            (issues #4 y #5)
        └─> observabilidad (JSONL): qa.jsonl + feedback.jsonl
```

Se eligió **FastAPI + frontend estático propio** (sin framework JS, sin CDN) en
vez de Streamlit: es más liviano para una VM chica (issue #7), permite una UI
responsiva a medida y deja la **API expuesta** para integraciones. Cohere corre
en la nube, así que no se carga ningún modelo pesado en la instancia.

## 2. Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/` | Sirve la interfaz de chat (`static/index.html`). |
| `POST` | `/api/ask` | `{question, category?, conversation_id?}` → respuesta + fuentes + confianza. |
| `POST` | `/api/feedback` | `{conversation_id, message_id, rating(+1/-1), comment?}` → registra feedback. |
| `GET` | `/api/metrics` | Resumen de mantenimiento (volumen, % sin respuesta, feedback, latencia). |
| `GET` | `/api/health` | Healthcheck para el deploy (issue #7). |

El `RagAgent` (Chroma + clientes Cohere) se construye **una sola vez** (lazy
singleton) y se reutiliza entre requests.

## 3. La interfaz (decisiones del issue)

- **Aviso de IA**: banner permanente que aclara que las respuestas son generadas
  y pueden tener errores → verificar las fuentes.
- **Fuentes**: cada respuesta muestra *chips* con las fuentes **citadas** (solo
  las que el modelo usó, ver `docs/05`).
- **Confianza**: indicador de color (alta/media/baja) según la similitud.
- **Feedback**: botones 👍/👎 por respuesta → `POST /api/feedback`.
- **Historial**: la conversación se guarda en memoria por `conversation_id` en el
  servidor y se persiste en `localStorage` del navegador (sobrevive recargas).
- **Responsivo**: layout flex con unidades relativas; se adapta a móvil.

## 4. Mantenimiento y monitoreo

`rag/observability.py` registra en **JSON Lines**:

- `data/logs/qa.jsonl` — una línea por pregunta (con `no_answer`, `confidence`,
  `sources`, `latency_ms`, `model`).
- `data/feedback/feedback.jsonl` — una línea por 👍/👎.

Las **preguntas sin respuesta** y el **feedback negativo** quedan marcados: son
el insumo para la **curaduría** del contenido y el ciclo de mejora. El endpoint
`/api/metrics` (y `rag metrics`) los agregan. Esta base la amplía el issue #8
(observabilidad centralizada en la nube).

### Actualización automática de documentos

El pipeline de ingesta ya detecta cambios (issue #2): basta correr `ingest`
periódicamente para reindexar solo lo que cambió. Ejemplo de cron diario:

```cron
0 3 * * *  cd /ruta/al/proyecto && PYTHONPATH=src:.venv-libs python3 -m rag ingest >> data/logs/ingest.log 2>&1
```

## 5. Comandos

```bash
export PYTHONPATH="src:.venv-libs"

# Levantar la interfaz web (http://localhost:8000)
python3 -m rag serve
python3 -m rag serve --port 9000 --reload   # dev con recarga en caliente

# Ver métricas de mantenimiento por consola
python3 -m rag metrics
```

Equivalente directo con uvicorn:

```bash
PYTHONPATH=src:.venv-libs uvicorn rag.web.app:app --host 0.0.0.0 --port 8000
```

## 6. Configuración (variables de entorno)

| Variable | Default | Qué controla |
|---|---|---|
| `RAG_LOG_DIR` | `data/logs` | Carpeta de logs de Q&A. |
| `RAG_FEEDBACK_DIR` | `data/feedback` | Carpeta del feedback. |

(Las variables de generación están en `docs/05`.)

## 7. Qué sigue

- **Issue #7 (OCI)**: contenerizar (Docker) y publicar; `/api/health` ya sirve de
  healthcheck.
- **Issue #8 (observabilidad)**: centralizar estos logs JSONL en la nube y sumar
  paneles de métricas.
