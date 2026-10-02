"""Ingest specific documents into ChromaDB by file name.

Usage (run from the project root with the server stopped):
    python -m scripts.ingest_files <file_name> [<file_name> ...]

Files are looked up anywhere under DOCUMENTS_DIR (including subfolders such as queue-emails/).
"""

import sys

from src.cli import create_components


def main(file_names: list[str]) -> int:
    file_manager, pipeline, _, indexer, _ = create_components()

    files = {f.name: f for f in file_manager.scan_documents()}
    failed = 0
    for name in file_names:
        target = files.get(name)
        if not target:
            print(f"NOT FOUND: {name}")
            failed += 1
            continue

        print(f"Ingesting {name} ...")
        result = pipeline.ingest_file(target.path)
        if result.get("status") == "success":
            print(f"  OK: {result['chunks']} chunks")
        else:
            print(f"  ERROR: {result.get('error')}")
            failed += 1

    print(f"\nTotal chunks in ChromaDB: {indexer.get_stats()['total_chunks']}")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
