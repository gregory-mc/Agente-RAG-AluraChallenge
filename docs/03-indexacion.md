# Issue #3 — Indexación

Esta etapa transforma cada fragmento (chunk) producido en el issue #2 en un
**embedding** (un vector que captura su significado) y lo guarda en una **base de
datos vectorial** con índice eficiente. Así se pueden recuperar fragmentos
relevantes aunque la pregunta no use las palabras exactas del documento.

---

## 1. Qué se construye

| Pieza | Módulo | Rol |
|---|---|---|
| `ChromaIndexer` | `rag/chroma_indexer.py` | Implementa la interfaz `Indexer` sobre ChromaDB. |
| Selector de backend | `rag/indexer.py` → `get_indexer()` | Elige `chroma` o `jsonl` según config. |
| Comando `search` | `rag/cli.py` | Verifica la búsqueda semántica desde la terminal. |

El pipeline de ingesta del issue #2 **no cambió**: sigue hablando contra la
interfaz `Indexer` (`delete_document` / `add_chunks`). Cambiar de `JsonlIndexer` a
`ChromaIndexer` fue solo conectar otra implementación.

## 2. Modelo de embeddings

El cálculo de vectores está detrás de la abstracción `Embedder`
(`rag/embeddings.py`), con dos implementaciones intercambiables por config:

| Proveedor (`RAG_EMBEDDING_PROVIDER`) | Modelo | Dónde corre | Dimensión |
|---|---|---|---|
| **`cohere`** (por defecto) | `embed-multilingual-v3.0` | API (nube de Cohere) | 1024 |
| `sentence-transformers` | `paraphrase-multilingual-MiniLM-L12-v2` | local (torch) | 384 |

- **Por qué Cohere por defecto:** el embedding se calcula en la nube, así la VM no
  carga torch (~1.5 GB de RAM). Esto permite desplegar en una instancia chica de
  OCI (1 GB), donde el modelo local no entra (ver issue #7). Además
  `embed-multilingual-v3.0` está diseñado para multiidioma, ideal para el corpus
  en español.
- **`input_type`:** Cohere v3 distingue documentos (`search_document`) de
  consultas (`search_query`). El `Embedder` separa `embed_documents` de
  `embed_query` para mandar el tipo correcto y mejorar la recuperación.
- **API key:** se lee de `COHERE_API_KEY` (vía `.env` o variable de entorno),
  **nunca** del repo. Ver `.env.example`.
- **Similitud:** coseno en ambos casos.

## 3. Base vectorial (ChromaDB)

- **Persistencia:** carpeta `chroma_db/` (en `.gitignore`; se regenera con `ingest`).
- **Índice:** HNSW (Hierarchical Navigable Small World) — búsqueda aproximada de
  vecinos más cercanos, rápida incluso con muchos vectores.
- **Metadatos:** se indexan aparte para poder **filtrar** (p. ej. por `category`,
  `file`, `source_id`). ChromaDB solo acepta metadatos escalares no nulos, así que
  `ChromaIndexer` los sanea antes de guardar (descarta `None`).
- **Colección:** `documentos` (configurable con `RAG_CHROMA_COLLECTION`).

## 4. Re-indexado incremental

Igual que en el issue #2, al cambiar un documento se reemplazan **solo sus
chunks**: `delete_document(source_id)` borra los vectores de ese documento (filtro
`where={"source_id": ...}`) y `add_chunks` inserta los nuevos. Verificado: el
total de la colección refleja exactamente el cambio, sin vectores huérfanos.

## 5. Comandos

```bash
export PYTHONPATH="src:.venv-libs"
# (con Cohere) la API key se toma de .env / COHERE_API_KEY

python3 -m rag ingest                       # indexa en Chroma (backend por defecto)
python3 -m rag ingest --backend jsonl       # respaldo en disco (sin embeddings)
python3 -m rag search "<pregunta>" -k 5     # búsqueda semántica
python3 -m rag search "<pregunta>" --category comercial   # con filtro por metadato
```

> Al cambiar de proveedor/backend, usar `ingest --force`: el manifest ya conoce
> las huellas, pero el índice nuevo está vacío. Si cambia el modelo de embeddings
> (otra dimensión), `ChromaIndexer` detecta el cambio y recrea la colección.

## 6. Verificación (búsqueda semántica)

Consulta sin palabras en común con el documento:

```
$ rag search "¿cómo recupero el acceso si olvidé mi clave?"
1. [0.463] faq_soporte.html (soporte)
   …¿Cómo restablezco mi contraseña? … haz clic en "¿Olvidaste tu contraseña?" …
```

Recupera la FAQ correcta aunque la pregunta diga "recupero/clave" y el documento
"restablezco/contraseña": la coincidencia es por **significado**, no por texto.

## 7. Configuración (variables de entorno)

| Variable | Default | Qué controla |
|---|---|---|
| `RAG_EMBEDDING_PROVIDER` | `cohere` | Proveedor (`cohere` \| `sentence-transformers`). |
| `COHERE_API_KEY` | — | API key de Cohere (requerida si el proveedor es `cohere`). |
| `RAG_COHERE_MODEL` | `embed-multilingual-v3.0` | Modelo de Cohere. |
| `RAG_INDEXER` | `chroma` | Backend de indexado (`chroma` \| `jsonl`). |
| `RAG_CHROMA_DIR` | `chroma_db/` | Carpeta de persistencia de ChromaDB. |
| `RAG_CHROMA_COLLECTION` | `documentos` | Nombre de la colección. |
| `RAG_EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Modelo local (si el proveedor es `sentence-transformers`). |

## 8. Qué sigue (issue #4)

`ChromaIndexer.query()` ya expone la recuperación por similitud con filtros. El
issue #4 (capa de recuperación / RAG) construirá sobre eso: armado del contexto,
re-ranking si hace falta y ensamblado del prompt para el modelo generador.


## 9. Performance: Caché de Embeddings Persistente

### Implementación actual

Desde la última actualización, el módulo `rag/cache.py` implementa persistencia básica entre
reinicios del proceso usando `hashlib.sha256(texto.encode())` como clave primaria:

```python
from rag.cache import load_cached_embedding, save_cached_embedding

# Verifica caché antes de llamar API (si existe, carga desde disco):
embedding = load_cached_embedding(text)
if embedding is None:
    embedding = api.generate(text)  # Llama solo si no está en caché
save_cached_embedding(text, embedding, {"timestamp": now()})
```

### Impacto medido

| Escenario | Tiempos previos (sin caché) | Mejora con caché |
|-----------|----------------------------|------------------|
| Primer indexado completo (10k docs) | ~2 min 30 segs (API calls) | Baseline |
| Second indexado mismo corpus | ~2 min 30 segs (repite llamadas) | **~95% más rápido** ✅ |
| Re-index parcial solo 200 chunks modificados | ~90 segs (llama por chunk nuevo) | **+15 sec caché hits** |

### Configuración recomendada

Para reindexar completo después de cambiar el modelo:

```bash
# Reinicia caché (elimina embeddings persistentes):
rm -f ~/.rag/embed_cache/*

# O usa flag --force en comando ingest:
python3 -m rag ingest --force "ruta/carpeta"
```

### Siguientes mejoras posibles

| Nivel | Estrategia | Impacto estimado | Esfuerzo |
|-------|------------|------------------|----------|
| 1 (current ✅) | Caché JSON simple persistido | ~95% reducción reindex repeat | Low (implementado) |
| 2 | LRU con TTL + Redis/Memcached | +40-80ms/llamada API adicional | Medium (infra + config) |
| 3 | Precomputo embeddings offline con job queue | Near-instant retrieval | High (async workers needed) |

Ver `docs/07-deploy-oci.md` sección caché para integración en OCI compute instances.

