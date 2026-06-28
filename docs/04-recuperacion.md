# Issue #4 — Capa de recuperación (RAG)

Dada una pregunta, esta etapa recupera los fragmentos más relevantes del índice y
arma el **contexto** que usará el generador (issue #5). Busca el equilibrio que
pide el issue: **velocidad** (búsqueda vectorial) + **calidad** (reranking).

---

## 1. Pipeline

```
pregunta ──> búsqueda vectorial (N candidatos) ──> filtro por metadatos
         ──> reranking (top_k) ──> contexto con citas a la fuente
```

| Paso | Módulo | Qué hace |
|---|---|---|
| Búsqueda | `ChromaIndexer.query` | Embebe la pregunta y trae los `N` vecinos más cercanos (rápido, aproximado). |
| Filtro | `where={...}` | Restringe por metadatos (ej. `category`) en la misma búsqueda. |
| Reranking | `rag/reranking.py` | Reordena los candidatos con un modelo más preciso y deja los `top_k`. |
| Contexto | `Retriever._build_context` | Concatena los fragmentos numerados con su fuente, hasta un presupuesto de caracteres. |

Orquestado por `Retriever.retrieve()` en `rag/retrieval.py`, que devuelve un
`RetrievalResult` con los chunks, el `context` ensamblado y la lista de `sources`.

## 2. Por qué dos etapas (vector + rerank)

- La **búsqueda vectorial** es O(log n) con HNSW: trae muchos candidatos (por
  defecto 20) en milisegundos, pero es *aproximada* — compara embeddings
  pre-calculados.
- El **reranking** (cross-encoder) mira la pregunta y cada candidato *juntos*, es
  más preciso pero más caro. Por eso se aplica solo a los 20 candidatos y no a
  todo el índice.

Traer muchos rápido y afinar los pocos finales = velocidad + calidad.

### Evidencia de que el rerank mejora el orden

Para *"soporte 24/7 para empresas grandes"*:

| Posición | Solo vector | Tras rerank |
|---|---|---|
| 3º | `integraciones_api.json` | `faq_soporte.html` ⬆ |
| 4º | `faq_soporte.html` | `integraciones_api.json` ⬇ |

El reranker subió la FAQ de soporte por encima de la doc de API, que es lo
correcto para esa pregunta.

> Nota: los scores absolutos de `rerank-multilingual-v3.0` no están calibrados a
> un rango fijo; lo que importa es el **orden relativo**.

## 3. Reranking (intercambiable)

Igual que los embeddings, el reranker está detrás de una abstracción
(`Reranker`) con dos implementaciones:

| Proveedor (`RAG_RERANK_PROVIDER`) | Implementación | Notas |
|---|---|---|
| `cohere` (default) | `rerank-multilingual-v3.0` vía API | Más preciso, multiidioma. |
| `none` | `PassthroughReranker` | Conserva el orden vectorial; sin costo de API (fallback). |

## 4. Comandos

```bash
export PYTHONPATH="src:.venv-libs"

# Búsqueda vectorial cruda (sin rerank) — útil para comparar
python3 -m rag search "<pregunta>" -k 5

# Recuperación completa (vector + rerank + contexto)
python3 -m rag retrieve "<pregunta>" -k 3
python3 -m rag retrieve "<pregunta>" --category comercial   # con filtro
python3 -m rag retrieve "<pregunta>" --context              # muestra el contexto ensamblado
```

## 5. Contexto ensamblado

`build_context` numera cada fragmento y antepone su fuente, respetando un
presupuesto de caracteres (`RAG_CONTEXT_MAX_CHARS`, default 4000):

```
[1] (fuente: .../comercial/comparativa_planes.csv)
caracteristica: precio_usuario_mes_usd; Free: 0; Pro: 9; Business: 18; ...

[2] (fuente: .../comercial/planes_y_precios.xlsx)
# Hoja: Planes y Precios
Plan | Precio mensual ... | Business | 18 | 180 | Empresas con varios equipos
```

Las citas `[n]` permiten que el generador (issue #5) **referencie las fuentes** en
la respuesta, requisito de un buen RAG corporativo.

## 6. Configuración (variables de entorno)

| Variable | Default | Qué controla |
|---|---|---|
| `RAG_RERANK_PROVIDER` | `cohere` | Reranker (`cohere` \| `none`). |
| `RAG_RERANK_MODEL` | `rerank-multilingual-v3.0` | Modelo de reranking. |
| `RAG_RETRIEVAL_CANDIDATES` | `20` | Candidatos de la búsqueda vectorial. |
| `RAG_RETRIEVAL_TOP_K` | `5` | Fragmentos finales tras el rerank. |
| `RAG_CONTEXT_MAX_CHARS` | `4000` | Tamaño máximo del contexto. |

## 7. Qué sigue (issue #5)

`RetrievalResult.context` + `sources` es la entrada del generador: se arma el
prompt (pregunta + contexto), se llama al modelo de lenguaje y se valida que la
respuesta se apoye en las fuentes citadas.
