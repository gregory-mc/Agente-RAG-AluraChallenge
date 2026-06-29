# Issue #5 — Producción y validación de respuestas

El generador recibe la **pregunta** + el **contexto** recuperado (issue #4) y
produce la respuesta en lenguaje natural, **siempre citando la fuente**. El foco
del issue es **reducir alucinaciones**.

---

## 1. Pipeline

```
pregunta ──> recuperación (#4) ──> umbral de confianza ──> generación (LLM) ──> respuesta + fuentes
                                        │
                                        └─ si baja: "no encontré información" (no se llama al LLM)
```

Orquestado por `RagAgent.answer()` en `rag/answering.py`. Es el único punto de
entrada que usan el CLI (`rag ask`) y la interfaz web (issue #6).

| Paso | Módulo | Qué hace |
|---|---|---|
| Recuperación | `Retriever.retrieve` | Trae los fragmentos y arma el contexto con citas `[n]`. |
| Confianza | `answering._confidence` | Mejor similitud vectorial entre los fragmentos. |
| Generación | `rag/generation.py` | Llama al LLM con el contexto y devuelve la respuesta + fuentes citadas. |

## 2. Control de alucinaciones

Tres mecanismos combinados:

1. **Anclaje al contexto (prompt).** El `SYSTEM_PROMPT` obliga a responder
   *solo* con el contexto entregado, prohíbe usar conocimiento externo y exige
   citar cada afirmación con `[n]`.
2. **Umbral de confianza.** Antes de llamar al LLM se mide la **similitud
   vectorial** del mejor fragmento. Si queda por debajo de `RAG_CONFIDENCE_MIN`
   (default `0.4`), el agente **no llama al modelo** y responde el mensaje de
   "no sé". Referencia empírica en este corpus: ~0.56 dentro del corpus, ~0.34
   fuera.

   > Se usa la similitud vectorial y **no** el `rerank_score`: el score del
   > reranker no está calibrado a un rango fijo (ver `docs/04`), solo sirve para
   > ordenar. La similitud coseno sí es comparable contra un umbral.
3. **"No sé" explícito.** Si el contexto no alcanza, la respuesta es
   exactamente `RAG_NO_ANSWER_MESSAGE`, en vez de inventar.

## 3. Fuentes citadas

`generation._cited_sources` parsea los marcadores `[n]` (incluye `[1,2]`) de la
respuesta y devuelve **solo las fuentes efectivamente citadas**, mapeando
`[n] → RetrievalResult.sources[n-1]`. Así la respuesta indica siempre el origen
y no se listan fuentes que el modelo no usó.

## 4. Generador intercambiable

Mismo patrón que `embeddings`/`reranking` (`get_generator()`):

| Proveedor (`RAG_GENERATION_PROVIDER`) | Implementación | Notas |
|---|---|---|
| `cohere` (default) | `chat` de Cohere (Command-R) vía API | Misma `COHERE_API_KEY` que embeddings y rerank. |
| `echo` | `EchoGenerator` | Sin LLM: arma la respuesta desde el contexto. Para dev/tests sin gastar API. |

## 5. Comandos

```bash
export PYTHONPATH="src:.venv-libs"

# Preguntar al agente (recuperación + generación)
python3 -m rag ask "¿Qué incluye el plan Business y cuánto cuesta?"
python3 -m rag ask "<pregunta>" --category comercial   # con filtro

# Sin gastar API (modo echo)
RAG_GENERATION_PROVIDER=echo python3 -m rag ask "<pregunta>"
```

## 6. Configuración (variables de entorno)

| Variable | Default | Qué controla |
|---|---|---|
| `RAG_GENERATION_PROVIDER` | `cohere` | Generador (`cohere` \| `echo`). |
| `RAG_GEN_MODEL` | `command-r-08-2024` | Modelo de chat de Cohere. |
| `RAG_GEN_TEMPERATURE` | `0.2` | Temperatura (baja = más fiel al contexto). |
| `RAG_CONFIDENCE_MIN` | `0.4` | Similitud mínima para llamar al LLM. |
| `RAG_NO_ANSWER_MESSAGE` | *"No encontré…"* | Texto exacto del "no sé". |

## 7. Qué sigue (issue #6)

`RagAgent.answer()` devuelve un `Answer` (texto, fuentes, confianza, `no_answer`,
latencia) que alimenta la interfaz web de chat: muestra la respuesta, las fuentes
citadas, el aviso de que es IA y los botones de feedback.
