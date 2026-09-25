"""CLI interface for the RAG POC — interactive document Q&A from the terminal."""

import sys
import logging

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

from configs.settings import get_settings
from src.ingestion.file_manager import FileManager
from src.ingestion.document_processor import DocumentProcessor
from src.ingestion.chunker import Chunker
from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer
from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.search_client import SearchClient
from src.retrieval.query_engine import QueryEngine

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def create_components():
    """Initialize all pipeline components from settings."""
    settings = get_settings()

    file_manager = FileManager(settings.documents_dir)
    processor = DocumentProcessor()
    chunker = Chunker(
        max_tokens=settings.max_chunk_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )
    embedder = Embedder(
        api_key=settings.gemini_api_key,
        model=settings.gemini_embed_model,
    )
    indexer = Indexer(settings.chroma_db_dir)

    pipeline = IngestionPipeline(
        file_manager=file_manager,
        processor=processor,
        chunker=chunker,
        embedder=embedder,
        indexer=indexer,
    )

    search_client = SearchClient(embedder=embedder, indexer=indexer)
    query_engine = QueryEngine(
        search_client=search_client,
        api_key=settings.gemini_api_key,
        llm_model=settings.gemini_llm_model,
        fallback_models=settings.fallback_models_list,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        top_k=settings.top_k_results,
    )

    return file_manager, pipeline, query_engine, indexer, settings


def show_status(file_manager: FileManager, indexer: Indexer, settings):
    """Display system status."""
    fm_stats = file_manager.get_stats()
    idx_stats = indexer.get_stats()

    table = Table(title="📊 System Status", show_header=False, border_style="dim")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Documents", str(fm_stats["total_files"]))
    table.add_row("Ingested", str(fm_stats["ingested_files"]))
    table.add_row("Pending", str(fm_stats["pending_files"]))
    table.add_row("Total Chunks", str(idx_stats["total_chunks"]))
    table.add_row("LLM Model", settings.gemini_llm_model)
    table.add_row("Embed Model", settings.gemini_embed_model)
    table.add_row("Documents Dir", str(settings.documents_path))

    console.print(table)


def main():
    """Main CLI entry point."""
    console.print(
        Panel.fit(
            "[bold white]🔍 RAG System POC[/bold white]\n"
            "[dim]Gemini-Powered Document Intelligence & Retrieval[/dim]",
            border_style="bright_blue",
        )
    )

    try:
        file_manager, pipeline, query_engine, indexer, settings = create_components()
    except Exception as e:
        console.print(f"[red]❌ Initialization failed: {e}[/red]")
        console.print("[dim]Make sure you have a valid .env file with GEMINI_API_KEY set.[/dim]")
        sys.exit(1)

    console.print()
    show_status(file_manager, indexer, settings)

    console.print(
        "\n[dim]Commands: [bold]ingest[/bold] | [bold]status[/bold] | "
        "[bold]clear[/bold] | [bold]quit[/bold][/dim]"
    )
    console.print("[dim]Or type any question to query your documents.[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]>[/bold cyan]").strip()

            if not user_input:
                continue

            match user_input.lower():
                case "quit" | "exit" | "q":
                    console.print("[dim]Goodbye! 👋[/dim]")
                    break

                case "ingest":
                    pipeline.ingest_all()
                    console.print()

                case "ingest --force":
                    pipeline.ingest_all(force=True)
                    console.print()

                case "status":
                    console.print()
                    show_status(file_manager, indexer, settings)
                    console.print()

                case "clear":
                    indexer.clear()
                    console.print("[yellow]🗑️ Index cleared.[/yellow]\n")

                case _:
                    # Treat as a query
                    console.print()
                    with console.status("[bold blue]Thinking...[/bold blue]"):
                        response = query_engine.query(user_input)

                    # Display answer
                    console.print(
                        Panel(
                            Markdown(response.answer),
                            title="📝 Answer",
                            border_style="green",
                        )
                    )

                    # Display sources
                    if response.sources:
                        console.print("[bold]📄 Sources:[/bold]")
                        for src in response.sources:
                            page = src.get("page_number", "?")
                            console.print(
                                f"  • {src['file_name']} (page {page})"
                            )

                    console.print(
                        f"\n[dim]({response.chunks_retrieved} chunks retrieved, "
                        f"model: {response.model})[/dim]\n"
                    )

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")


if __name__ == "__main__":
    main()
