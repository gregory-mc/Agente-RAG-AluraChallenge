# Issue #8 — Registrar la ejecución del proyecto

Dejar registro de lo que hace Techie en producción para **auditar, depurar y
mejorar**: logs estructurados (local y en la nube), versionado de modelos y
prompts, y un panel de métricas (latencia, errores, tokens).

---

## 1. Doble destino de cada evento

`rag/observability.py` emite cada evento a **dos destinos** a la vez:

| Destino | Para qué |
|---|---|
| **stdout en JSON** (1 línea por evento) | En la nube, el stdout del contenedor lo captura **OCI Logging** sin montar volúmenes. Se apaga con `RAG_LOG_STDOUT=0`. |
| **Archivos JSON Lines** | Auditoría local / volumen: `data/logs/qa.jsonl`, `data/logs/errors.jsonl`, `data/feedback/feedback.jsonl`. |

Eventos registrados: `qa` (cada pregunta), `feedback` (👍/👎), `error` (fallos del
agente) y `request` (traza HTTP método/ruta/status/latencia, solo a stdout).

Ejemplo de línea en stdout (lo que ve OCI Logging):
```json
{"ts":"2026-06-28T21:59:…","event":"qa","git_sha":"test123","question":"¿Cuánto cuesta el plan Pro?",
 "no_answer":false,"confidence":0.62,"sources":["…/planes_y_precios.xlsx"],
 "model":"cohere:command-r-08-2024","prompt_version":"2026-06-v2","tokens":1439,"latency_ms":2006}
```

## 2. Versionado de modelos y prompt

Para saber **qué generó qué**, cada respuesta registra:
- **Modelos**: embeddings, reranking y generación (de `config`).
- **Versión de prompt**: `generation.PROMPT_VERSION` (subir al cambiar el system prompt).
- **Versión de app y commit**: `APP_VERSION` y `GIT_SHA` (los inyecta el build/CI).

Consultable en vivo en **`GET /api/version`**:
```json
{"app_version":"0.4.0","git_sha":"<sha>",
 "models":{"embedding":"cohere:embed-multilingual-v3.0","rerank":"cohere:rerank-multilingual-v3.0",
           "generation":"cohere:command-r-08-2024"},
 "prompt_version":"2026-06-v2"}
```
El `GIT_SHA` se hornea en la imagen vía `--build-arg GIT_SHA=…` (lo pasa el workflow
de CI con `${{ github.sha }}`).

## 3. Métricas y panel

- **`GET /api/metrics`**: total de preguntas, % sin respuesta, feedback +/−,
  latencia media y **p95**, **tokens** acumulados y **errores**.
- **`GET /panel`**: panel web de observabilidad (tarjetas + versión en ejecución),
  se refresca cada 5 s. Útil para la demo y el material multimedia.
- **CLI**: `python3 -m rag metrics` imprime el mismo resumen por consola.

## 4. Versionado con Git / DVC

- **Código y configuración**: versionados con **Git** (este repo). El `GIT_SHA` que
  corre en la nube se ve en `/api/version`, así se puede atar un comportamiento a un
  commit exacto.
- **Datos** (`data/documents/`, `chroma_db/`): el corpus es chico y va en Git. Si
  creciera, se recomienda **DVC** para versionar datos/artefactos sin inflar el repo.

## 5. En la nube (OCI)

- Los `event` JSON de stdout los recoge **OCI Logging** desde la Container Instance
  (configurar un Log Group/Log y, si se quiere, búsquedas y alertas).
- Con OCI Logging se pueden armar **paneles** y **alarmas** (p. ej. tasa de errores
  o de `no_answer` alta) en Monitoring.

> **Obligatorio del issue:** registrar la ejecución en la nube con **material
> multimedia** — grabar un video/capturas del agente respondiendo en OCI, del
> `/panel` y de los logs en OCI Logging. (Este paso es manual, lo hace el autor.)

## 6. Variables de entorno

| Variable | Default | Qué controla |
|---|---|---|
| `RAG_LOG_STDOUT` | `1` | Emitir eventos JSON a stdout (apagar con `0`). |
| `APP_VERSION` | `0.4.0` | Versión de la app reportada. |
| `GIT_SHA` | `dev` | Commit en ejecución (lo inyecta el CI). |
| `RAG_LOG_DIR` | `data/logs` | Carpeta de `qa.jsonl` / `errors.jsonl`. |
| `RAG_FEEDBACK_DIR` | `data/feedback` | Carpeta de `feedback.jsonl`. |
