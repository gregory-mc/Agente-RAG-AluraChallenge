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
    results = ingest_all(force=args.force)
    indexed = [r for r in results if r.status == "indexed"]
    unchanged = [r for r in results if r.status == "unchanged"]
    errors = [r for r in results if r.status == "error"]

    for r in indexed:
        print(f"✓ indexado   {r.source_id}  ({r.chunks} chunks)")
    for r in unchanged:
        print(f"• sin cambios {r.source_id}")
    for r in errors:
        print(f"✗ error      {r.source_id}: {r.detail}", file=sys.stderr)

    print(
        f"\nResumen: {len(indexed)} indexados, {len(unchanged)} sin cambios, "
        f"{len(errors)} con error.  Índice: {config.CHUNKS_PATH}"
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
    p_ing.set_defaults(func=_cmd_ingest)

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
