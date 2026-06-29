"""CLI del pipeline de ingesta (issue #2).

Comandos:
    add-url <url>     registra una URL para vigilarla
    ingest [--force]  procesa todo; re-procesa solo lo que cambió
    check             reporta qué documentos cambiaron (sin re-indexar)
    list              lista las fuentes registradas y su estado
"""
from __future__ import annotations

import argparse
import sys

from . import config, manifest as manifest_mod
from .extractors import supported_extensions
from .indexer import get_indexer
from .ingest import discover_local_sources, ingest_all
from .sources import UrlSource


def _cmd_add_url(args) -> int:
    src = UrlSource(args.url, category=args.category, source_id=args.id)
    manifest = manifest_mod.load()
    is_new = manifest_mod.register_url(
        manifest, source_id=src.source_id, url=src.url, category=src.category
    )
    manifest_mod.save(manifest)
    if is_new:
        print(f"✓ URL registrada: {src.source_id}  (categoría: {src.category})")
        print("  Ejecutá 'ingest' para procesarla.")
    else:
        print(f"• La URL ya estaba registrada: {src.source_id}")
    return 0


def _cmd_ingest(args) -> int:
    indexer = get_indexer(args.backend)
    results = ingest_all(indexer=indexer, force=args.force)
    indexed = [r for r in results if r.status == "indexed"]
    unchanged = [r for r in results if r.status == "unchanged"]
    errors = [r for r in results if r.status == "error"]

    for r in indexed:
        print(f"✓ indexado   {r.source_id}  ({r.chunks} chunks)")
    for r in unchanged:
        print(f"• sin cambios {r.source_id}")
    for r in errors:
        print(f"✗ error      {r.source_id}: {r.detail}", file=sys.stderr)

    backend = args.backend or config.INDEXER_BACKEND
    location = config.CHROMA_DIR if backend == "chroma" else config.CHUNKS_PATH
    embedder = getattr(indexer, "embedder", None)
    extra = f"  Embeddings: {embedder.name}" if embedder else ""
    print(
        f"\nResumen: {len(indexed)} indexados, {len(unchanged)} sin cambios, "
        f"{len(errors)} con error.  Backend: {backend} ({location}){extra}"
    )
    return 1 if errors else 0


def _cmd_check(args) -> int:
    from .sources import UrlSource as _Url

    manifest = manifest_mod.load()
    sources = list(discover_local_sources())
    for entry in manifest_mod.url_sources(manifest):
        sources.append(_Url(entry["url"], category=entry.get("category", "online"),
                            source_id=entry["source_id"]))

    changed = new = same = 0
    for src in sources:
        known = manifest_mod.get_entry(manifest, src.source_id)
        try:
            fetch = src.fetch(known)
        except Exception as exc:
            print(f"✗ error      {src.source_id}: {exc}", file=sys.stderr)
            continue
        if known is None:
            print(f"+ nuevo      {src.source_id}")
            new += 1
        elif fetch.changed:
            print(f"~ cambió     {src.source_id}")
            changed += 1
        else:
            print(f"• igual      {src.source_id}")
            same += 1
    print(f"\n{new} nuevos, {changed} cambiados, {same} sin cambios.")
    return 0


def _cmd_search(args) -> int:
    from .chroma_indexer import ChromaIndexer

    indexer = ChromaIndexer()
    total = indexer.count()
    if total == 0:
        print("El índice está vacío. Ejecutá 'ingest' primero.", file=sys.stderr)
        return 1

    where = {"category": args.category} if args.category else None
    hits = indexer.query(args.query, n_results=args.k, where=where)
    print(f"Consulta: {args.query!r}  (índice: {total} chunks)\n")
    for i, hit in enumerate(hits, start=1):
        md = hit["metadata"]
        # distancia coseno -> similitud aproximada (a menor distancia, más relevante)
        sim = 1 - hit["distance"]
        snippet = " ".join(hit["text"].split())[:200]
        print(f"{i}. [{sim:.3f}] {md.get('file')}  (categoría: {md.get('category')})")
        print(f"   {snippet}…\n")
    return 0


def _cmd_retrieve(args) -> int:
    from .retrieval import Retriever

    retriever = Retriever()
    where = {"category": args.category} if args.category else None
    result = retriever.retrieve(args.query, top_k=args.k, where=where)

    if not result.chunks:
        print("Sin resultados. ¿Indexaste con 'ingest'?", file=sys.stderr)
        return 1

    print(f"Consulta: {result.query!r}")
    print(f"Reranker: {retriever.reranker.name}\n")
    print("Fragmentos recuperados (tras reranking):")
    for i, chunk in enumerate(result.chunks, start=1):
        score = f"{chunk.rerank_score:.3f}" if chunk.rerank_score is not None else "—"
        snippet = " ".join(chunk.text.split())[:160]
        print(f"  {i}. [rerank {score}] {chunk.metadata.get('file')} ({chunk.metadata.get('category')})")
        print(f"     {snippet}…")

    if args.context:
        print("\n--- Contexto ensamblado (para el generador, issue #5) ---")
        print(result.context)
    return 0


def _cmd_ask(args) -> int:
    from .answering import RagAgent

    agent = RagAgent()
    result = agent.answer(args.query, category=args.category)

    conf = f"{result.confidence:.3f}" if result.confidence is not None else "—"
    print(f"Pregunta: {args.query!r}")
    print(f"Modelo: {result.model}  |  Confianza: {conf}\n")
    print(result.text)
    if result.sources:
        print("\nFuentes:")
        for i, src in enumerate(result.sources, start=1):
            print(f"  [{i}] {src}")
    if result.suggestions:
        print("\nQuizás también quieras preguntar:")
        for s in result.suggestions:
            print(f"  • {s}")
    return 0


def _cmd_serve(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Falta dependencia: uvicorn (pip install -r requirements.txt)", file=sys.stderr)
        return 1
    print(f"Levantando la interfaz web en http://{args.host}:{args.port}  (Ctrl-C para salir)")
    uvicorn.run("rag.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_metrics(args) -> int:
    from . import observability

    data = observability.metrics()
    print("Métricas de ejecución (issues #6/#8):")
    print(f"  Preguntas totales   : {data['total_questions']}")
    print(f"  Sin respuesta       : {data['unanswered']} ({data['unanswered_rate']:.0%})")
    print(f"  Feedback 👍 / 👎     : {data['feedback_positive']} / {data['feedback_negative']}")
    print(f"  Latencia media/p95  : {data['avg_latency_ms']} / {data['p95_latency_ms']} ms")
    print(f"  Tokens (acumulado)  : {data['total_tokens']}")
    print(f"  Errores             : {data['errors']}")
    return 0


def _cmd_list(args) -> int:
    manifest = manifest_mod.load()
    sources = manifest.get("sources", {})
    if not sources:
        print("(no hay fuentes registradas todavía)")
        return 0
    for source_id, entry in sources.items():
        print(
            f"[{entry.get('kind'):5}] {source_id}\n"
            f"        categoría={entry.get('category')} "
            f"chunks={entry.get('chunk_count')} "
            f"última_ingesta={entry.get('last_ingested')}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_url = sub.add_parser("add-url", help="registrar una URL para vigilar")
    p_url.add_argument("url")
    p_url.add_argument("--category", default="online", help="categoría de negocio")
    p_url.add_argument("--id", default=None, help="source_id explícito (opcional)")
    p_url.set_defaults(func=_cmd_add_url)

    p_ing = sub.add_parser("ingest", help="procesar todo; re-procesa lo que cambió")
    p_ing.add_argument("--force", action="store_true", help="re-procesar aunque no haya cambios")
    p_ing.add_argument("--backend", choices=("chroma", "jsonl"), default=None,
                       help="backend de indexado (por defecto: el de config)")
    p_ing.set_defaults(func=_cmd_ingest)

    p_sr = sub.add_parser("search", help="búsqueda vectorial cruda (sin reranking)")
    p_sr.add_argument("query", help="texto a buscar")
    p_sr.add_argument("-k", type=int, default=5, help="cantidad de resultados")
    p_sr.add_argument("--category", default=None, help="filtrar por categoría")
    p_sr.set_defaults(func=_cmd_search)

    p_rt = sub.add_parser("retrieve", help="recuperación completa (vector + rerank + contexto)")
    p_rt.add_argument("query", help="pregunta")
    p_rt.add_argument("-k", type=int, default=config.RETRIEVAL_TOP_K, help="fragmentos finales")
    p_rt.add_argument("--category", default=None, help="filtrar por categoría")
    p_rt.add_argument("--context", action="store_true", help="mostrar el contexto ensamblado")
    p_rt.set_defaults(func=_cmd_retrieve)

    p_ask = sub.add_parser("ask", help="preguntar al agente (recuperación + generación)")
    p_ask.add_argument("query", help="pregunta")
    p_ask.add_argument("--category", default=None, help="filtrar por categoría")
    p_ask.set_defaults(func=_cmd_ask)

    p_srv = sub.add_parser("serve", help="levantar la interfaz web de chat")
    p_srv.add_argument("--host", default="0.0.0.0", help="host de escucha")
    p_srv.add_argument("--port", type=int, default=8000, help="puerto")
    p_srv.add_argument("--reload", action="store_true", help="recarga en caliente (dev)")
    p_srv.set_defaults(func=_cmd_serve)

    p_met = sub.add_parser("metrics", help="resumen de mantenimiento (preguntas, feedback)")
    p_met.set_defaults(func=_cmd_metrics)

    p_chk = sub.add_parser("check", help="reportar cambios sin re-indexar")
    p_chk.set_defaults(func=_cmd_check)

    p_ls = sub.add_parser("list", help="listar fuentes registradas")
    p_ls.set_defaults(func=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
