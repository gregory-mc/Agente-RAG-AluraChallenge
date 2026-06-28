# Issue #2 — Proceso y extracción de contenido

Esta etapa convierte los documentos (locales **y online**) en texto limpio,
fragmentado y con metadatos, listo para generar embeddings (issue #3). Además
**detecta cuándo un documento cambió y re-procesa solo ese documento**,
reemplazando sus fragmentos en el índice (re-indexado incremental).

---

## 1. Pipeline

```
fuente ──> fetch (detecta cambios) ──> extraer ──> limpiar ──> chunkear
       ──> metadatos ──> re-indexado incremental (delete + add)
```

| Paso | Módulo | Qué hace |
|---|---|---|
| Fuente | `rag/sources/` | De dónde sale el documento: `LocalSource` (archivo) o `UrlSource` (URL HTTP). |
| Fetch | `Source.fetch()` | Resuelve la fuente a un archivo local y calcula su **huella** para saber si cambió. |
| Extraer | `rag/extractors/` | Texto plano según el formato (8 formatos soportados). |
| Limpiar | `rag/cleaning.py` | Normaliza Unicode, espacios y saltos de línea; quita caracteres de control. |
| Chunkear | `rag/chunking.py` | Divide en fragmentos de ~1000 caracteres con 150 de solapamiento, respetando párrafos y oraciones. |
| Metadatos | `rag/metadata.py` | Asigna a cada chunk: categoría, archivo, fecha, autor, título, ubicación, formato, posición. |
| Indexar | `rag/indexer.py` | Hook hacia la base vectorial. Hoy `JsonlIndexer` (respaldo); el issue #3 aportará `ChromaIndexer`. |

## 2. Formatos soportados

| Formato | Extensión | Librería |
|---|---|---|
| PDF | `.pdf` | `pypdf` |
| Word | `.docx` | `python-docx` |
| Excel | `.xlsx` | `openpyxl` |
| PowerPoint | `.pptx` | `python-pptx` |
| Markdown | `.md` | nativo (limpieza de sintaxis) |
| CSV | `.csv` | `csv` (stdlib, detecta delimitador) |
| JSON | `.json` | `json` (stdlib, aplanado `clave: valor`) |
| HTML | `.html` | `beautifulsoup4` (quita `script`/`style`/`nav`/…) |

## 3. Documentos online y detección de cambios

Un documento online se registra una vez y luego se vigila on-demand:

```bash
rag add-url "https://ejemplo.com/manual.pdf" --category producto
rag ingest            # procesa lo nuevo / lo que cambió
```

La detección de cambios usa **dos mecanismos complementarios**:

1. **Validadores HTTP** — en el `fetch` se envía `If-None-Match` (ETag) e
   `If-Modified-Since` (Last-Modified). Si el servidor responde `304 Not
   Modified`, el documento no cambió y no se re-descarga.
2. **Hash del contenido** (SHA-256) — respaldo cuando el servidor no da
   validadores. Si el hash difiere del guardado, el documento cambió.

El estado conocido de cada documento (huella, validadores, nº de chunks, fecha de
última ingesta) vive en `data/state/manifest.json`.

### Re-indexado incremental

Cuando un documento cambia, **solo ese documento** se re-procesa: el `Indexer`
borra sus chunks viejos (filtrando por el metadato `source_id`) e inserta los
nuevos. Los demás documentos no se tocan. Esto evita reconstruir todo el índice y
mantiene la coherencia (sin fragmentos huérfanos).

## 4. Comandos (CLI)

```bash
export PYTHONPATH="src:.venv-libs"     # entorno local de este repo

python3 -m rag add-url <url> [--category C] [--id ID]   # registrar una URL
python3 -m rag check                                    # ¿qué cambió? (no re-indexa)
python3 -m rag ingest [--force]                         # procesar; re-procesa lo que cambió
python3 -m rag list                                     # fuentes registradas y su estado
```

## 5. Estructura del proyecto

```
src/rag/
├── config.py            # rutas y parámetros (overridables por env)
├── models.py            # ExtractedDoc, Chunk
├── cleaning.py          # limpieza de texto
├── chunking.py          # fragmentación con solapamiento
├── metadata.py          # metadatos + id estable de chunk
├── indexer.py           # interfaz Indexer + JsonlIndexer (stub issue #3)
├── manifest.py          # estado de cambios + registro de URLs
├── ingest.py            # orquestador del pipeline
├── cli.py               # interfaz de línea de comandos
├── extractors/          # un extractor por formato + registry
└── sources/             # LocalSource, UrlSource
```

## 6. Instalación y prueba

```bash
pip3 install --target .venv-libs -r requirements.txt
export PYTHONPATH="src:.venv-libs"
python3 -m rag ingest        # indexa los 8 documentos de data/documents/
```

Salida y estado (`data/state/`) están en `.gitignore`: se regeneran ejecutando la
ingesta.

## 7. Decisiones de diseño

- **Hook `Indexer` en vez de embeddings acá:** la generación de vectores es el
  issue #3. La ingesta entrega chunks contra una interfaz; cambiar a ChromaDB no
  toca el pipeline.
- **Chunking por caracteres:** simple y sin dependencia del tokenizador del
  modelo de embeddings (que se define en el issue #3/#4). Respeta límites de
  párrafo y oración para no cortar ideas.
- **Detección on-demand (no daemon):** un comando que se puede correr a mano o
  desde cron/CI. Sin servidor que mantener; encaja con el deploy en OCI (issue #7).
- **`source_id` estable:** clave del re-indexado incremental y de la futura cita
  de fuentes en las respuestas (issues #4 y #5).
