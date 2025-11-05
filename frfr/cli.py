"""
Command-line interface for Frfr.
"""

import sys
import os
import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table

from frfr.documents import extract_pdf_to_text, get_pdf_info
from frfr.extraction.fact_extractor import FactExtractor
from frfr.session import Session
from frfr.validation import validate_consolidated_facts


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Frfr: High-confidence document Q&A using LLM swarm consensus."""
    pass


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option(
    "--min-text-threshold",
    default=50,
    help="Minimum characters to consider PyPDF2 extraction successful",
)
@click.option(
    "--save-metadata",
    is_flag=True,
    help="Save extraction metadata (PDF source info) alongside text file",
)
def extract(pdf_path: str, output_path: str, min_text_threshold: int, save_metadata: bool):
    """
    Extract text from a PDF file.

    PDF_PATH: Path to the input PDF file
    OUTPUT_PATH: Path to save the extracted text file
    """
    console.print("\n[bold blue]📄 PDF Text Extraction[/bold blue]\n")

    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    # Get PDF info
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Analyzing PDF...", total=None)
        try:
            info = get_pdf_info(pdf_path)
        except Exception as e:
            console.print(f"[red]✗ Error reading PDF: {e}[/red]")
            sys.exit(1)

    console.print(f"[green]✓[/green] PDF found: [cyan]{pdf_path.name}[/cyan]")
    console.print(f"  Pages: {info['pages']}")
    console.print(f"  Encrypted: {info['is_encrypted']}")
    console.print(f"  Size: {info['file_size']:,} bytes\n")

    # Extract text
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Extracting text from {info['pages']} pages...", total=None)
        try:
            result = extract_pdf_to_text(
                pdf_path=pdf_path,
                output_path=output_path,
                min_text_threshold=min_text_threshold,
            )
        except Exception as e:
            console.print(f"\n[red]✗ Extraction failed: {e}[/red]")
            sys.exit(1)

    console.print(f"\n[green]✓ Extraction complete![/green]")
    console.print(f"  Method: [cyan]{result['method']}[/cyan]")
    console.print(f"  Pages: {result['pages']}")
    console.print(f"  Characters: {result['total_chars']:,}")
    console.print(f"  Output: [cyan]{result['output_file']}[/cyan]")
    console.print(f"  Source PDF: [cyan]{result.get('source_pdf', 'N/A')}[/cyan]\n")

    # Save metadata if requested
    if save_metadata:
        metadata_path = Path(output_path).with_suffix('.json')
        import json
        metadata = {
            "source_pdf": result.get('source_pdf'),
            "source_pdf_path": result.get('source_pdf_path'),
            "extraction_method": result['method'],
            "pages": result['pages'],
            "total_chars": result['total_chars'],
            "text_file": result['output_file'],
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        console.print(f"[green]✓[/green] Metadata saved: [cyan]{metadata_path}[/cyan]\n")

    # Preview
    console.print("[bold]Preview (first 500 characters):[/bold]")
    console.print("[dim]" + "─" * 60 + "[/dim]")
    with open(output_path, "r") as f:
        preview = f.read(500)
        console.print(preview)
    console.print("[dim]" + "─" * 60 + "[/dim]\n")

    console.print("[green]✅ Success![/green] Text file ready for processing.\n")


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
def info(pdf_path: str):
    """
    Display metadata about a PDF file.

    PDF_PATH: Path to the PDF file
    """
    console.print("\n[bold blue]📄 PDF Information[/bold blue]\n")

    pdf_path = Path(pdf_path)

    try:
        info = get_pdf_info(pdf_path)
    except Exception as e:
        console.print(f"[red]✗ Error reading PDF: {e}[/red]")
        sys.exit(1)

    console.print(f"File: [cyan]{pdf_path.name}[/cyan]")
    console.print(f"Path: [dim]{pdf_path}[/dim]")
    console.print(f"\nPages: {info['pages']}")
    console.print(f"Encrypted: {info['is_encrypted']}")
    console.print(f"Size: {info['file_size']:,} bytes")
    console.print(f"Size: {info['file_size'] / 1024 / 1024:.2f} MB\n")


@main.command("extract-facts")
@click.argument("text_file", type=click.Path(exists=True))
@click.option("--document-name", help="Name of the document (defaults to filename)")
@click.option("--session-id", help="Session ID (creates new if not provided)")
@click.option("--chunk-size", default=500, help="Lines per chunk (default: 500)")
@click.option("--overlap", default=100, help="Overlap lines between chunks (default: 100)")
@click.option("--start-chunk", default=0, help="Start extraction from this chunk (for resume)")
@click.option("--end-chunk", default=None, type=int, help="End extraction at this chunk (inclusive)")
@click.option("--max-workers", default=5, help="Maximum parallel Claude processes (default: 5)")
@click.option("--multipass", is_flag=True, help="Enable multi-pass extraction (CUECs, test procedures, quantitative, technical specs)")
def extract_facts_cmd(
    text_file: str,
    document_name: str,
    session_id: str,
    chunk_size: int,
    overlap: int,
    start_chunk: int,
    end_chunk: int,
    max_workers: int,
    multipass: bool,
):
    """
    Extract structured facts from a document using LLM.

    TEXT_FILE: Path to the extracted text file (output from 'extract' command)

    This command:
    1. Generates a structured summary of the document
    2. Chunks the document with sliding window (default: 500 lines, 100 overlap)
    3. Extracts facts from each chunk using the summary as context
    4. Saves all artifacts in a session directory

    Requires Claude CLI to be installed and authenticated (run 'claude login').
    """
    console.print("\n[bold blue]🔍 Fact Extraction Pipeline[/bold blue]\n")

    text_file = Path(text_file)
    if not document_name:
        document_name = text_file.stem

    # Create session
    session = Session(session_id=session_id)
    console.print(f"[green]✓[/green] Session: [cyan]{session.session_id}[/cyan]")
    console.print(f"  Directory: [dim]{session.session_dir}[/dim]\n")

    # Initialize extractor
    console.print(f"[green]✓[/green] Using Claude CLI")
    console.print(f"  Chunk size: {chunk_size} lines")
    console.print(f"  Overlap: {overlap} lines")
    console.print(f"  Max parallel workers: {max_workers}")
    if multipass:
        console.print(f"  [cyan]Multi-pass extraction: ENABLED[/cyan] (will run specialized passes for CUECs, tests, quantitative, technical specs)")
    if start_chunk > 0 or end_chunk is not None:
        chunk_range = f"{start_chunk}"
        if end_chunk is not None:
            chunk_range += f"-{end_chunk}"
        else:
            chunk_range += "+"
        console.print(f"  [yellow]Chunk range: {chunk_range}[/yellow]")

    extractor = FactExtractor(
        chunk_size=chunk_size,
        overlap_size=overlap,
        max_workers=max_workers,
    )

    # Calculate total chunks to provide better progress info
    with open(text_file, "r") as f:
        text = f.read()
    chunks = extractor.chunk_text(text)
    total_chunks = len(chunks)
    total_lines = len(text.split('\n'))

    # Calculate chunks to be processed
    if end_chunk is not None:
        chunks_to_process = end_chunk - start_chunk + 1
    else:
        chunks_to_process = total_chunks - start_chunk

    console.print(f"  Document: {total_lines:,} lines → {total_chunks} chunks")
    console.print(f"  Processing: {chunks_to_process} chunks (chunk {start_chunk} to {end_chunk if end_chunk else total_chunks-1})")
    console.print()

    # Run extraction with progress bar
    try:
        # Track running totals
        running_facts = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Processing chunks...", total=chunks_to_process)

            def update_progress(current, total, message):
                nonlocal running_facts
                # Extract fact count from message
                import re
                match = re.search(r'(\d+) facts validated', message)
                if match:
                    chunk_facts = int(match.group(1))
                    running_facts += chunk_facts
                    desc = f"[cyan]Chunk {start_chunk + current}/{start_chunk + total} • {running_facts} facts extracted"
                else:
                    desc = f"[cyan]{message}"
                progress.update(task, completed=current, description=desc)

            result = extractor.extract_from_document(
                text_file=text_file,
                document_name=document_name,
                session=session,
                start_chunk=start_chunk,
                end_chunk=end_chunk,
                progress_callback=update_progress,
                enable_multipass=multipass,
            )

        # Display results
        console.print("\n[green]✅ Extraction complete![/green]\n")

        # Create summary table
        table = Table(title="Extraction Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Document", document_name)
        table.add_row("Model", result.model_used)
        table.add_row("Total Facts", str(len(result.facts)))
        table.add_row("Chunks Processed", f"{chunks_to_process}/{total_chunks}")
        table.add_row("Facts per Chunk", f"{len(result.facts)/chunks_to_process:.1f} avg")
        table.add_row("Session ID", session.session_id)

        console.print(table)
        console.print()

        # Show sample facts
        if result.facts:
            console.print("[bold]Sample Facts (first 3):[/bold]\n")
            for i, fact in enumerate(result.facts[:3], 1):
                console.print(f"[cyan]{i}.[/cyan] [bold]{fact.claim}[/bold]")
                console.print(f"   Location: [dim]{fact.source_location}[/dim]")
                console.print(f"   Confidence: {fact.confidence:.2f}")
                console.print(f"   Evidence: [italic]\"{fact.evidence_quote[:100]}...\"[/italic]")
                console.print()

        # Show session stats
        stats = session.get_stats()
        console.print(f"[dim]Session directory: {stats['session_dir']}[/dim]")
        console.print(f"[dim]Total chunks: {stats['total_chunks']}[/dim]")
        console.print(f"[dim]Total fact files: {stats['total_fact_files']}[/dim]\n")

        # Auto-consolidate facts
        console.print("[bold blue]📦 Consolidating facts...[/bold blue]\n")

        # Load summary and all facts
        summary = session.load_summary(document_name)
        facts_list = session.load_all_facts(document_name)

        # Create consolidated structure with source tracking
        consolidated = {
            "session_id": session.session_id,
            "documents": {
                document_name: {
                    "summary": summary,
                    "facts": facts_list,
                    "fact_count": len(facts_list),
                    "source_text_file": str(text_file),  # Track the text file used
                }
            },
            "total_facts": len(facts_list),
        }

        # Save to output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{document_name}_facts.json"

        import json
        with open(output_file, "w") as f:
            json.dump(consolidated, f, indent=2)

        console.print(f"[green]✓[/green] Consolidated facts saved: [cyan]{output_file}[/cyan]\n")

    except Exception as e:
        console.print(f"\n[red]✗ Extraction failed: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command("consolidate-facts")
@click.argument("session_id", type=str)
@click.option("--output", "-o", help="Output file path (default: session_dir/consolidated_facts.json)")
@click.option("--document-name", help="Consolidate facts for specific document only")
def consolidate_facts_cmd(session_id: str, output: str, document_name: str):
    """
    Consolidate all extracted facts from a session into a single document.

    SESSION_ID: The session ID (e.g., sess_ac43e048b916)
    """
    console.print("\n[bold blue]📦 Consolidating Facts[/bold blue]\n")

    # Load session
    try:
        session = Session(session_id=session_id)
        console.print(f"[green]✓[/green] Session loaded: [cyan]{session.session_id}[/cyan]")
        console.print(f"  Directory: [dim]{session.session_dir}[/dim]\n")
    except Exception as e:
        console.print(f"[red]✗ Session not found: {e}[/red]\n")
        sys.exit(1)

    # Get all documents in session
    docs = session.metadata.get("documents", [])
    if not docs:
        console.print("[yellow]⚠ No documents found in session[/yellow]\n")
        sys.exit(1)

    # Filter by document name if specified
    if document_name:
        if document_name not in docs:
            console.print(f"[red]✗ Document '{document_name}' not found in session[/red]")
            console.print(f"Available documents: {', '.join(docs)}\n")
            sys.exit(1)
        docs = [document_name]

    console.print(f"Documents to consolidate: [cyan]{', '.join(docs)}[/cyan]\n")

    # Consolidate facts
    consolidated = {
        "session_id": session.session_id,
        "documents": {},
        "total_facts": 0,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading facts...", total=len(docs))

        for doc in docs:
            # Load summary
            summary = session.load_summary(doc)

            # Load all facts for document
            facts = session.load_all_facts(doc)

            consolidated["documents"][doc] = {
                "summary": summary,
                "facts": facts,
                "fact_count": len(facts),
            }
            consolidated["total_facts"] += len(facts)

            progress.advance(task)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = session.session_dir / "consolidated_facts.json"

    # Save consolidated facts
    import json
    with open(output_path, "w") as f:
        json.dump(consolidated, f, indent=2)

    console.print(f"\n[green]✅ Consolidation complete![/green]\n")

    # Display summary
    table = Table(title="Consolidated Facts Summary")
    table.add_column("Document", style="cyan")
    table.add_column("Facts", style="green", justify="right")
    table.add_column("Summary Available", style="yellow")

    for doc, data in consolidated["documents"].items():
        has_summary = "✓" if data["summary"] else "✗"
        table.add_row(doc, str(data["fact_count"]), has_summary)

    console.print(table)
    console.print()
    console.print(f"[bold]Total Facts:[/bold] {consolidated['total_facts']}")
    console.print(f"[bold]Output:[/bold] [cyan]{output_path}[/cyan]\n")


@main.command("validate-facts")
@click.argument("consolidated_file", type=click.Path(exists=True))
@click.argument("text_file", type=click.Path(exists=True))
@click.option("--show-invalid-only", is_flag=True, help="Only show invalid facts")
@click.option("--output", "-o", help="Save validation report to JSON file")
def validate_facts_cmd(
    consolidated_file: str, text_file: str, show_invalid_only: bool, output: str
):
    """
    Validate extracted facts against source text.

    CONSOLIDATED_FILE: Path to consolidated_facts.json
    TEXT_FILE: Path to the original source text file

    This command verifies that all evidence quotes actually exist in the
    specified line ranges of the source document.
    """
    console.print("\n[bold blue]✓ Validating Facts[/bold blue]\n")

    consolidated_path = Path(consolidated_file)
    text_path = Path(text_file)

    console.print(f"[green]✓[/green] Consolidated facts: [cyan]{consolidated_path.name}[/cyan]")
    console.print(f"[green]✓[/green] Source text: [cyan]{text_path.name}[/cyan]\n")

    # Run validation
    try:
        with console.status("[bold green]Validating facts..."):
            results, stats = validate_consolidated_facts(consolidated_path, text_path)

        # Display summary
        console.print("[green]✅ Validation complete![/green]\n")

        # Summary table
        summary_table = Table(title="Validation Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green", justify="right")

        summary_table.add_row("Total Facts", str(stats["total_facts"]))
        summary_table.add_row("Valid Facts", str(stats["valid_facts"]))
        summary_table.add_row(
            "Near Match Facts",
            f"[yellow]{stats.get('near_match_facts', 0)}[/yellow]"
            if stats.get("near_match_facts", 0) > 0
            else "0",
        )
        summary_table.add_row(
            "Invalid Facts",
            f"[red]{stats['invalid_facts']}[/red]"
            if stats["invalid_facts"] > 0
            else "0",
        )
        summary_table.add_row(
            "Validation Rate", f"{stats['validation_rate']:.1%}"
        )
        summary_table.add_row(
            "Near Match Rate", f"{stats.get('near_match_rate', 0):.1%}"
        )

        console.print(summary_table)
        console.print()

        # Show detailed results
        if stats["invalid_facts"] > 0 or stats.get("near_match_facts", 0) > 0 or not show_invalid_only:
            results_table = Table(title="Validation Details")
            results_table.add_column("#", style="dim", width=4)
            results_table.add_column("Status", width=12)
            results_table.add_column("Claim", style="cyan")
            results_table.add_column("Issue / Match %", style="yellow")

            for result in results:
                # Skip valid facts if showing invalid only
                if show_invalid_only and result.is_valid:
                    continue

                if result.is_valid:
                    status = "[green]✓ VALID[/green]"
                    match_info = f"{result.match_percentage:.0%}" if result.match_percentage else "100%"
                elif result.is_near_match:
                    status = "[yellow]~ NEAR[/yellow]"
                    match_info = f"{result.match_percentage:.0%} - {result.error_message[:30]}..." if len(result.error_message) > 30 else result.error_message
                else:
                    status = "[red]✗ INVALID[/red]"
                    match_info = result.error_message[:40] + "..." if len(result.error_message) > 40 else result.error_message

                results_table.add_row(
                    str(result.fact_index + 1),
                    status,
                    result.claim[:60] + "..." if len(result.claim) > 60 else result.claim,
                    match_info,
                )

            console.print(results_table)
            console.print()

        # Save report if requested
        if output:
            output_path = Path(output)
            report = {
                "summary": stats,
                "results": [
                    {
                        "index": r.fact_index,
                        "claim": r.claim,
                        "is_valid": r.is_valid,
                        "is_near_match": r.is_near_match,
                        "match_percentage": r.match_percentage,
                        "error_message": r.error_message,
                        "line_range": r.actual_line_range,
                        "quote_snippet": r.quote_snippet,
                    }
                    for r in results
                ],
            }

            import json
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)

            console.print(f"[green]✓[/green] Validation report saved: [cyan]{output_path}[/cyan]\n")

        # Exit with error if any facts invalid (but not for near matches)
        if stats["invalid_facts"] > 0:
            console.print(
                f"[yellow]⚠ Warning: {stats['invalid_facts']} fact(s) failed validation[/yellow]\n"
            )
            sys.exit(1)
        elif stats.get("near_match_facts", 0) > 0:
            console.print(
                f"[yellow]⚠ Note: {stats['near_match_facts']} fact(s) are near matches (~75-89% match)[/yellow]\n"
            )

    except Exception as e:
        console.print(f"\n[red]✗ Validation failed: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command("session-info")
@click.argument("session_id", type=str)
@click.option("--document-name", help="Show info for specific document only")
def session_info_cmd(session_id: str, document_name: str):
    """
    Display information about a session.

    SESSION_ID: The session ID (e.g., sess_ac43e048b916)
    """
    console.print("\n[bold blue]📊 Session Information[/bold blue]\n")

    # Load session
    try:
        session = Session(session_id=session_id)
        console.print(f"[green]✓[/green] Session: [cyan]{session.session_id}[/cyan]")
        console.print(f"  Directory: [dim]{session.session_dir}[/dim]\n")
    except Exception as e:
        console.print(f"[red]✗ Session not found: {e}[/red]\n")
        sys.exit(1)

    # Get session stats
    stats = session.get_stats()

    # Display metadata
    console.print("[bold]Metadata:[/bold]")
    console.print(f"  Status: [cyan]{session.metadata.get('status', 'unknown')}[/cyan]")
    console.print(f"  Created: [dim]{session.metadata.get('created_at', 'unknown')}[/dim]")
    if "completed_at" in session.metadata:
        console.print(f"  Completed: [dim]{session.metadata.get('completed_at')}[/dim]")
    console.print()

    # Get documents
    docs = session.metadata.get("documents", [])
    if document_name:
        if document_name not in docs:
            console.print(f"[red]✗ Document '{document_name}' not found in session[/red]")
            console.print(f"Available documents: {', '.join(docs)}\n")
            sys.exit(1)
        docs = [document_name]

    if not docs:
        console.print("[yellow]⚠ No documents in session[/yellow]\n")
        sys.exit(0)

    # Create per-document table
    doc_table = Table(title="Documents")
    doc_table.add_column("Document", style="cyan")
    doc_table.add_column("Processed Chunks", style="green")
    doc_table.add_column("Last Chunk", style="yellow", justify="right")
    doc_table.add_column("Total Facts", style="magenta", justify="right")
    doc_table.add_column("Has Summary", style="blue")

    for doc in docs:
        processed_chunks = session.get_processed_chunks(doc)
        total_facts = len(session.load_all_facts(doc))
        has_summary = "✓" if session.load_summary(doc) else "✗"

        if processed_chunks:
            chunk_range = f"{min(processed_chunks)}-{max(processed_chunks)}"
            last_chunk = str(max(processed_chunks))
        else:
            chunk_range = "none"
            last_chunk = "-"

        doc_table.add_row(doc, chunk_range, last_chunk, str(total_facts), has_summary)

    console.print(doc_table)
    console.print()

    # Show how to resume
    if docs:
        for doc in docs:
            processed_chunks = session.get_processed_chunks(doc)
            if processed_chunks:
                next_chunk = max(processed_chunks) + 1
                console.print(f"[bold]To resume '{doc}':[/bold]")
                console.print(
                    f"  [dim]python frfr/cli.py extract-facts <text_file> "
                    f"--document-name {doc} "
                    f"--session-id {session.session_id} "
                    f"--start-chunk {next_chunk}[/dim]\n"
                )


@main.command("correct-quotes")
@click.argument("session_id", type=str)
@click.argument("text_file", type=click.Path(exists=True))
@click.option("--document-name", required=True, help="Document name to correct")
@click.option("--min-match", default=0.3, help="Minimum match threshold (0.0-1.0, default: 0.3)")
@click.option("--output", "-o", help="Output file for corrected facts (default: session_dir/corrected_facts.json)")
def correct_quotes_cmd(session_id: str, text_file: str, document_name: str, min_match: float, output: str):
    """
    Correct paraphrased quotes in rejected facts using LLM assistance.

    SESSION_ID: The session ID containing rejected facts
    TEXT_FILE: Path to the original source text file

    This command attempts to recover facts that were rejected during extraction
    because the evidence quote was paraphrased instead of being exact. It uses
    the LLM to find the correct exact quote in the source text.
    """
    from frfr.validation.quote_corrector import QuoteCorrector

    console.print("\n[bold blue]🔧 Quote Correction Tool[/bold blue]\n")

    text_path = Path(text_file)

    # Load session
    try:
        session = Session(session_id=session_id)
        console.print(f"[green]✓[/green] Session: [cyan]{session.session_id}[/cyan]")
        console.print(f"  Directory: [dim]{session.session_dir}[/dim]\n")
    except Exception as e:
        console.print(f"[red]✗ Session not found: {e}[/red]\n")
        sys.exit(1)

    # Note: This requires integration with extraction pipeline to access rejected facts
    # For now, we'll provide a simpler file-based interface

    console.print(f"[yellow]⚠ Note: This command currently requires a facts file with rejection info[/yellow]\n")
    console.print(f"To use this tool:")
    console.print(f"  1. Export rejected facts during extraction")
    console.print(f"  2. Run: python -m frfr.validation.quote_corrector <rejected_facts.json> <text_file> <output.json>\n")

    # TODO: Implement full session integration
    console.print("[dim]Full session integration coming soon...[/dim]\n")


def _get_surrounding_context(location_str: str, source_lines: list, context_lines: int = 10) -> str:
    """
    Extract surrounding context from source document.

    Args:
        location_str: Location string like "Lines 1245-1248"
        source_lines: List of all source text lines
        context_lines: Number of lines before/after to include

    Returns:
        Surrounding context text
    """
    import re

    # Parse location string to get line numbers
    match = re.search(r'Lines? (\d+)(?:-(\d+))?', location_str, re.IGNORECASE)
    if not match:
        return ""

    start_line = int(match.group(1)) - 1  # Convert to 0-indexed
    end_line = int(match.group(2)) - 1 if match.group(2) else start_line

    # Calculate context window
    context_start = max(0, start_line - context_lines)
    context_end = min(len(source_lines), end_line + context_lines + 1)

    # Extract context
    context = "".join(source_lines[context_start:context_end])
    return context.strip()


@main.command("query")
@click.argument("facts_file", type=click.Path(exists=True))
@click.argument("question", type=str)
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive mode after answering")
@click.option("--show-facts", is_flag=True, help="Show supporting facts in output")
@click.option("--deep", is_flag=True, help="Deep search: include surrounding context from source document")
def query_cmd(facts_file: str, question: str, interactive: bool, show_facts: bool, deep: bool):
    """
    Query extracted facts to answer questions.

    FACTS_FILE: Path to consolidated facts JSON file
    QUESTION: Question to answer (e.g., "Does this vendor have SSO enabled?")

    This command searches through extracted facts and uses Claude to synthesize
    an answer with citations to supporting facts.

    Use --deep to include surrounding context from the source document for more
    detailed answers. Automatically finds the source text file.
    """
    import json
    import glob
    from frfr.extraction.claude_client import ClaudeClient

    console.print("\n[bold blue]🔍 Querying Knowledge Base[/bold blue]\n")

    facts_path = Path(facts_file)
    console.print(f"[green]✓[/green] Facts file: [cyan]{facts_path.name}[/cyan]")
    if deep:
        console.print(f"[green]✓[/green] Deep search: [cyan]enabled[/cyan] (will find source text)")
    console.print(f"[green]✓[/green] Question: [italic]\"{question}\"[/italic]\n")

    # Load facts
    try:
        with open(facts_path, "r") as f:
            data = json.load(f)

        # Extract facts from consolidated structure
        all_facts = []
        if "documents" in data:
            for doc_name, doc_data in data["documents"].items():
                all_facts.extend(doc_data.get("facts", []))
        elif "facts" in data:
            all_facts = data["facts"]
        else:
            console.print("[red]✗ Invalid facts file format[/red]\n")
            sys.exit(1)

        console.print(f"[dim]Loaded {len(all_facts)} facts[/dim]\n")
    except Exception as e:
        console.print(f"[red]✗ Error loading facts: {e}[/red]\n")
        sys.exit(1)

    # Load source text if deep search enabled
    source_lines = []
    if deep:
        # Try to find source text file automatically
        # First check if any facts have source_doc field
        source_doc_name = None
        for fact in all_facts[:5]:  # Check first few facts
            if "source_doc" in fact:
                source_doc_name = fact["source_doc"]
                break

        # Try common patterns to find the text file
        source_text_path = None
        search_patterns = []

        if source_doc_name:
            # Use source_doc name from facts
            base_name = Path(source_doc_name).stem
            search_patterns = [
                f"output/{base_name}*.txt",
                f"output/*{base_name}*.txt",
                f"{base_name}*.txt",
            ]

        # Also try pattern matching facts filename
        facts_base = facts_path.stem.replace("_facts", "").replace("_qv_tagged", "").replace("_filtered", "")
        search_patterns.extend([
            f"output/{facts_base}*.txt",
            f"output/*{facts_base}*.txt",
        ])

        # Search for source text file
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                source_text_path = matches[0]
                break

        if not source_text_path:
            console.print("[yellow]⚠ Warning: Could not find source text file automatically[/yellow]")
            console.print("[dim]Searched for patterns like: output/{document_name}*.txt[/dim]")
            console.print("[yellow]Continuing without deep search context...[/yellow]\n")
        else:
            try:
                with open(source_text_path, "r") as f:
                    source_lines = f.readlines()
                console.print(f"[green]✓[/green] Found source text: [cyan]{Path(source_text_path).name}[/cyan]")
                console.print(f"[dim]Loaded {len(source_lines)} lines for deep context[/dim]\n")
            except Exception as e:
                console.print(f"[yellow]⚠ Warning: Could not load source text: {e}[/yellow]\n")

    # Query facts with Claude
    try:
        with console.status("[bold green]Querying facts with Claude..."):
            claude = ClaudeClient()

            # Build prompt with facts
            facts_text = ""
            for i, fact in enumerate(all_facts, 1):
                claim = fact.get("claim", "")
                location = fact.get("source_location", "")

                # Get evidence quote (V4 or V5 format)
                evidence = ""
                if "evidence_quotes" in fact and fact["evidence_quotes"]:
                    # V5 format - get first quote
                    if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                        evidence = fact["evidence_quotes"][0].get("quote", "")
                elif "evidence_quote" in fact:
                    # V4 format
                    evidence = fact.get("evidence_quote", "")

                facts_text += f"{i}. {claim}\n"
                facts_text += f"   Location: {location}\n"
                if evidence:
                    evidence_preview = evidence[:150] + "..." if len(evidence) > 150 else evidence
                    facts_text += f"   Evidence: \"{evidence_preview}\"\n"

                # Add surrounding context for deep search
                if deep and source_lines:
                    context = _get_surrounding_context(location, source_lines, context_lines=10)
                    if context:
                        facts_text += f"   Context: {context[:300]}...\n"

                facts_text += "\n"

            deep_instruction = ""
            if deep:
                deep_instruction = """
DEEP SEARCH MODE: You have access to surrounding context from the source document for each fact.
Use this context to provide more detailed, nuanced answers. Look for additional details in the
context that may not be captured in the fact claim itself.
"""

            prompt = f"""You are answering a question based on extracted facts from a document.

QUESTION: {question}

AVAILABLE FACTS:
{facts_text}
{deep_instruction}
INSTRUCTIONS:
1. Search through the facts to find information relevant to the question
2. Provide a clear, direct answer with INLINE CITATIONS including source locations
3. Cite facts inline using [Fact N, Location] notation immediately after each claim
4. ALWAYS include the source location from the fact (e.g., "Lines 123-125") so the user can cross-check
5. If the facts don't contain enough information to answer, say so clearly
6. Be precise - only claim what the facts actually support{"" if not deep else " (including details from surrounding context)"}

Format your response as:
ANSWER: [your answer with inline citations including locations]
CONFIDENCE: [High/Medium/Low]

SOURCE REFERENCES:
[List each cited fact with its full location for easy cross-checking]

Example format:
ANSWER: Yes, the vendor supports SSO [Fact 42, Lines 1245-1248]. The implementation uses SAML 2.0 protocol [Fact 108, Lines 2103-2105] and integrates with Azure AD [Fact 234, Lines 3567-3569].
CONFIDENCE: High

SOURCE REFERENCES:
- Fact 42 (Lines 1245-1248): SSO configuration details
- Fact 108 (Lines 2103-2105): SAML 2.0 protocol implementation
- Fact 234 (Lines 3567-3569): Azure AD integration
"""

            response = claude.prompt(prompt)

        # Parse response
        console.print("[green]✅ Query complete![/green]\n")

        # Display answer
        console.print("[bold]Response:[/bold]")
        console.print(response)
        console.print()

        # Extract and display cited facts
        import re
        # Match both formats: [Fact N] and [Fact N, Lines X-Y]
        fact_citations = re.findall(r'\[Fact (\d+)(?:,\s*Lines [^\]]+)?\]', response)
        if fact_citations:
            # Get unique fact numbers in order of appearance
            seen = set()
            unique_citations = []
            for num_str in fact_citations:
                if num_str not in seen:
                    seen.add(num_str)
                    unique_citations.append(num_str)

            if show_facts or unique_citations:
                console.print("[bold]Cited Facts:[/bold]\n")
                for num_str in unique_citations:
                    try:
                        idx = int(num_str) - 1
                        if 0 <= idx < len(all_facts):
                            fact = all_facts[idx]
                            console.print(f"[cyan]Fact {num_str}:[/cyan] {fact.get('claim', '')}")
                            console.print(f"  [dim]Location: {fact.get('source_location', '')}[/dim]")

                            # Show evidence if available
                            evidence = ""
                            if "evidence_quotes" in fact and fact["evidence_quotes"]:
                                if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                                    evidence = fact["evidence_quotes"][0].get("quote", "")
                            elif "evidence_quote" in fact:
                                evidence = fact.get("evidence_quote", "")

                            if evidence:
                                evidence_preview = evidence[:200] + "..." if len(evidence) > 200 else evidence
                                console.print(f"  [dim]Evidence: \"{evidence_preview}\"[/dim]")
                            console.print()
                    except (ValueError, IndexError):
                        pass

        # DEEP SEARCH: Interactive fact exploration
        if deep and source_lines and fact_citations:
            console.print("[dim]─" * 60 + "[/dim]\n")
            console.print("[bold yellow]🔎 Deep Search Mode Enabled[/bold yellow]")
            console.print("[dim]Type a fact number to see surrounding context from the source document[/dim]")
            console.print("[dim]Type 'done' or press Enter to continue[/dim]\n")

            while True:
                try:
                    user_input = console.input("[bold cyan]Dig deeper into fact #:[/bold cyan] ").strip()

                    if not user_input or user_input.lower() in ['done', 'exit', 'q', 'quit']:
                        console.print()
                        break

                    # Parse fact number
                    try:
                        fact_num = int(user_input)
                        fact_idx = fact_num - 1

                        if fact_idx < 0 or fact_idx >= len(all_facts):
                            console.print(f"[yellow]⚠ Fact {fact_num} not found (valid range: 1-{len(all_facts)})[/yellow]\n")
                            continue

                        fact = all_facts[fact_idx]
                        location = fact.get('source_location', '')

                        # Get surrounding context
                        context = _get_surrounding_context(location, source_lines, context_lines=20)

                        if not context:
                            console.print(f"[yellow]⚠ Could not extract context for fact {fact_num}[/yellow]\n")
                            continue

                        # Display deep dive
                        console.print(f"\n[bold cyan]════ Fact {fact_num} Deep Dive ════[/bold cyan]\n")
                        console.print(f"[bold]Claim:[/bold] {fact.get('claim', '')}")
                        console.print(f"[dim]Location: {location}[/dim]\n")

                        # Show evidence quote
                        evidence = ""
                        if "evidence_quotes" in fact and fact["evidence_quotes"]:
                            if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                                evidence = fact["evidence_quotes"][0].get("quote", "")
                        elif "evidence_quote" in fact:
                            evidence = fact.get("evidence_quote", "")

                        if evidence:
                            console.print(f"[bold]Evidence Quote:[/bold]")
                            console.print(f"[italic]\"{evidence}\"[/italic]\n")

                        # Show surrounding context
                        console.print(f"[bold yellow]📖 Source Document Context (±20 lines):[/bold yellow]")
                        console.print(f"[dim]{'─' * 70}[/dim]")
                        console.print(f"[dim]{context}[/dim]")
                        console.print(f"[dim]{'─' * 70}[/dim]\n")

                    except ValueError:
                        console.print(f"[yellow]⚠ Please enter a fact number (e.g., '42') or 'done'[/yellow]\n")
                        continue

                except KeyboardInterrupt:
                    console.print("\n")
                    break
                except EOFError:
                    console.print("\n")
                    break

        # Interactive mode
        if interactive:
            console.print("[dim]─" * 60 + "[/dim]\n")
            console.print("[yellow]Interactive mode - Type your questions (or 'exit' to quit)[/yellow]\n")

            while True:
                try:
                    next_question = console.input("[bold cyan]Question:[/bold cyan] ")
                    if next_question.lower() in ['exit', 'quit', 'q']:
                        console.print("\n[dim]Goodbye![/dim]\n")
                        break

                    if not next_question.strip():
                        continue

                    # Query again with new question
                    console.print()
                    with console.status("[bold green]Querying..."):
                        prompt = f"""You are answering a question based on extracted facts from a document.

QUESTION: {next_question}

AVAILABLE FACTS:
{facts_text}

INSTRUCTIONS:
1. Search through the facts to find information relevant to the question
2. Provide a clear, direct answer with INLINE CITATIONS including source locations
3. Cite facts inline using [Fact N, Location] notation immediately after each claim
4. ALWAYS include the source location from the fact (e.g., "Lines 123-125") so the user can cross-check
5. If the facts don't contain enough information to answer, say so clearly
6. Be precise - only claim what the facts actually support

Format your response as:
ANSWER: [your answer with inline citations including locations]
CONFIDENCE: [High/Medium/Low]

SOURCE REFERENCES:
[List each cited fact with its full location for easy cross-checking]

Example format:
ANSWER: Yes, the vendor supports SSO [Fact 42, Lines 1245-1248]. The implementation uses SAML 2.0 protocol [Fact 108, Lines 2103-2105] and integrates with Azure AD [Fact 234, Lines 3567-3569].
CONFIDENCE: High

SOURCE REFERENCES:
- Fact 42 (Lines 1245-1248): SSO configuration details
- Fact 108 (Lines 2103-2105): SAML 2.0 protocol implementation
- Fact 234 (Lines 3567-3569): Azure AD integration
"""
                        response = claude.prompt(prompt)

                    console.print("\n[bold]Response:[/bold]")
                    console.print(response)
                    console.print()

                    # Show cited facts in interactive mode too
                    fact_citations = re.findall(r'\[Fact (\d+)\]', response)
                    if fact_citations:
                        seen = set()
                        unique_citations = []
                        for num_str in fact_citations:
                            if num_str not in seen:
                                seen.add(num_str)
                                unique_citations.append(num_str)

                        console.print("[bold]Cited Facts:[/bold]\n")
                        for num_str in unique_citations:
                            try:
                                idx = int(num_str) - 1
                                if 0 <= idx < len(all_facts):
                                    fact = all_facts[idx]
                                    console.print(f"[cyan]Fact {num_str}:[/cyan] {fact.get('claim', '')}")
                                    console.print(f"  [dim]Location: {fact.get('source_location', '')}[/dim]\n")
                            except (ValueError, IndexError):
                                pass

                except KeyboardInterrupt:
                    console.print("\n\n[dim]Goodbye![/dim]\n")
                    break
                except EOFError:
                    console.print("\n\n[dim]Goodbye![/dim]\n")
                    break

    except Exception as e:
        console.print(f"\n[red]✗ Query failed: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command("interactive")
@click.argument("facts_file", type=click.Path(exists=True))
@click.option("--show-facts", is_flag=True, help="Show supporting facts with each answer")
def interactive_cmd(facts_file: str, show_facts: bool):
    """
    Enter interactive query mode - ask questions about extracted facts.

    FACTS_FILE: Path to consolidated facts JSON file

    This command loads a facts file and drops you into an interactive REPL
    where you can ask natural language questions. Each answer includes
    citations to the supporting facts.

    Commands:
      - Type any question to get an answer
      - /stats - Show database statistics
      - /help - Show available commands
      - exit, quit, q - Exit interactive mode
    """
    import json
    import re
    from frfr.extraction.claude_client import ClaudeClient

    console.print("\n[bold blue]🔍 Interactive Query Mode[/bold blue]\n")

    facts_path = Path(facts_file)

    # Load facts
    try:
        with open(facts_path, "r") as f:
            data = json.load(f)

        # Extract facts from consolidated structure
        all_facts = []
        document_names = []
        if "documents" in data:
            for doc_name, doc_data in data["documents"].items():
                document_names.append(doc_name)
                all_facts.extend(doc_data.get("facts", []))
        elif "facts" in data:
            all_facts = data["facts"]
        else:
            console.print("[red]✗ Invalid facts file format[/red]\n")
            sys.exit(1)

        console.print(f"[green]✓[/green] Loaded [cyan]{len(all_facts)}[/cyan] facts from [cyan]{facts_path.name}[/cyan]")
        if document_names:
            console.print(f"[dim]Documents: {', '.join(document_names)}[/dim]")
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error loading facts: {e}[/red]\n")
        sys.exit(1)

    # Build facts text once (for reuse in all queries)
    facts_text = ""
    for i, fact in enumerate(all_facts, 1):
        claim = fact.get("claim", "")
        location = fact.get("source_location", "")

        # Get evidence quote (V4 or V5 format)
        evidence = ""
        if "evidence_quotes" in fact and fact["evidence_quotes"]:
            if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                evidence = fact["evidence_quotes"][0].get("quote", "")
        elif "evidence_quote" in fact:
            evidence = fact.get("evidence_quote", "")

        facts_text += f"{i}. {claim}\n"
        facts_text += f"   Location: {location}\n"
        if evidence:
            evidence_preview = evidence[:150] + "..." if len(evidence) > 150 else evidence
            facts_text += f"   Evidence: \"{evidence_preview}\"\n"
        facts_text += "\n"

    # Initialize Claude client
    try:
        claude = ClaudeClient()
    except Exception as e:
        console.print(f"[red]✗ Failed to initialize Claude: {e}[/red]\n")
        sys.exit(1)

    # Show help
    console.print("[bold]Interactive Mode Commands:[/bold]")
    console.print("  [cyan]/stats[/cyan]  - Show database statistics")
    console.print("  [cyan]/help[/cyan]   - Show this help message")
    console.print("  [cyan]exit[/cyan]    - Exit interactive mode")
    console.print()
    console.print("[yellow]Type your questions below:[/yellow]")
    console.print("[dim]─" * 60 + "[/dim]\n")

    # Interactive loop
    while True:
        try:
            question = console.input("[bold cyan]Question:[/bold cyan] ")

            # Handle exit commands
            if question.lower() in ['exit', 'quit', 'q']:
                console.print("\n[dim]Goodbye![/dim]\n")
                break

            # Handle empty input
            if not question.strip():
                continue

            # Handle special commands
            if question.startswith('/'):
                cmd = question.lower().strip()

                if cmd == '/stats':
                    console.print()
                    console.print("[bold]Database Statistics:[/bold]")
                    console.print(f"  Total facts: [cyan]{len(all_facts)}[/cyan]")

                    # Count by fact type
                    fact_types = {}
                    for fact in all_facts:
                        ft = fact.get("fact_type", "unknown")
                        fact_types[ft] = fact_types.get(ft, 0) + 1

                    console.print("\n  [bold]By Type:[/bold]")
                    for ft, count in sorted(fact_types.items(), key=lambda x: x[1], reverse=True):
                        console.print(f"    {ft}: {count}")

                    # Count facts with quantitative values
                    qv_count = sum(1 for f in all_facts if f.get("quantitative_values"))
                    console.print(f"\n  Facts with quantitative values: [cyan]{qv_count}[/cyan] ({qv_count/len(all_facts)*100:.1f}%)")

                    console.print()
                    continue

                elif cmd == '/help':
                    console.print()
                    console.print("[bold]Available Commands:[/bold]")
                    console.print("  [cyan]/stats[/cyan]  - Show database statistics")
                    console.print("  [cyan]/help[/cyan]   - Show this help message")
                    console.print("  [cyan]exit[/cyan]    - Exit interactive mode")
                    console.print("\n[bold]Tips:[/bold]")
                    console.print("  - Ask specific questions for better results")
                    console.print("  - Answers include [Fact N] citations")
                    console.print("  - Use --show-facts flag to see full cited facts")
                    console.print()
                    continue

                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
                    console.print("[dim]Type /help for available commands[/dim]\n")
                    continue

            # Query with Claude
            console.print()
            with console.status("[bold green]Querying..."):
                prompt = f"""You are answering a question based on extracted facts from a document.

QUESTION: {question}

AVAILABLE FACTS:
{facts_text}

INSTRUCTIONS:
1. Search through the facts to find information relevant to the question
2. Provide a clear, direct answer with INLINE CITATIONS including source locations
3. Cite facts inline using [Fact N, Location] notation immediately after each claim
4. ALWAYS include the source location from the fact (e.g., "Lines 123-125") so the user can cross-check
5. If the facts don't contain enough information to answer, say so clearly
6. Be precise - only claim what the facts actually support

Format your response as:
ANSWER: [your answer with inline citations including locations]
CONFIDENCE: [High/Medium/Low]

SOURCE REFERENCES:
[List each cited fact with its full location for easy cross-checking]

Example format:
ANSWER: Yes, the vendor supports SSO [Fact 42, Lines 1245-1248]. The implementation uses SAML 2.0 protocol [Fact 108, Lines 2103-2105] and integrates with Azure AD [Fact 234, Lines 3567-3569].
CONFIDENCE: High

SOURCE REFERENCES:
- Fact 42 (Lines 1245-1248): SSO configuration details
- Fact 108 (Lines 2103-2105): SAML 2.0 protocol implementation
- Fact 234 (Lines 3567-3569): Azure AD integration
"""
                response = claude.prompt(prompt, max_tokens=4000)

            # Display answer
            console.print("[bold]Response:[/bold]")
            console.print(response)
            console.print()

            # Extract and display cited facts
            fact_citations = re.findall(r'\[Fact (\d+)\]', response)
            if fact_citations and show_facts:
                # Get unique fact numbers in order of appearance
                seen = set()
                unique_citations = []
                for num_str in fact_citations:
                    if num_str not in seen:
                        seen.add(num_str)
                        unique_citations.append(num_str)

                console.print("[bold]Cited Facts:[/bold]\n")
                for num_str in unique_citations:
                    try:
                        idx = int(num_str) - 1
                        if 0 <= idx < len(all_facts):
                            fact = all_facts[idx]
                            console.print(f"[cyan]Fact {num_str}:[/cyan] {fact.get('claim', '')}")
                            console.print(f"  [dim]Location: {fact.get('source_location', '')}[/dim]")

                            # Show evidence if available
                            evidence = ""
                            if "evidence_quotes" in fact and fact["evidence_quotes"]:
                                if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                                    evidence = fact["evidence_quotes"][0].get("quote", "")
                            elif "evidence_quote" in fact:
                                evidence = fact.get("evidence_quote", "")

                            if evidence:
                                evidence_preview = evidence[:200] + "..." if len(evidence) > 200 else evidence
                                console.print(f"  [dim]Evidence: \"{evidence_preview}\"[/dim]")
                            console.print()
                    except (ValueError, IndexError):
                        pass

            console.print("[dim]─" * 60 + "[/dim]\n")

        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye![/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]Goodbye![/dim]\n")
            break
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]\n")
            # Continue the loop rather than exit


@main.command("process")
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--document-name", help="Name of the document (defaults to filename)")
@click.option("--chunk-size", default=500, help="Lines per chunk for fact extraction (default: 500)")
@click.option("--overlap", default=100, help="Overlap lines between chunks (default: 100)")
@click.option("--max-workers", default=5, help="Maximum parallel Claude processes (default: 5)")
@click.option("--multipass", is_flag=True, help="Enable multi-pass extraction")
@click.option("--skip-validation", is_flag=True, help="Skip fact validation step")
@click.option("--no-interactive", is_flag=True, help="Skip interactive mode (just process)")
@click.option("--show-facts", is_flag=True, help="Show supporting facts in interactive mode")
def process_cmd(
    pdf_path: str,
    document_name: str,
    chunk_size: int,
    overlap: int,
    max_workers: int,
    multipass: bool,
    skip_validation: bool,
    no_interactive: bool,
    show_facts: bool,
):
    """
    Process a PDF from start to finish: extract text, extract facts, validate, and query.

    PDF_PATH: Path to the input PDF file

    This supercommand combines all steps:
    1. Extract PDF to text
    2. Extract facts using LLM
    3. Validate facts against source
    4. Launch interactive query mode

    Example:
        frfr process documents/soc2_report.pdf
        frfr process documents/report.pdf --max-workers 11 --multipass
    """
    console.print("\n[bold blue]🚀 Frfr Complete Processing Pipeline[/bold blue]\n")

    pdf_path = Path(pdf_path)
    if not document_name:
        document_name = pdf_path.stem

    # Setup paths
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    text_file = output_dir / f"{document_name}_text.txt"
    facts_file = output_dir / f"{document_name}_facts.json"

    # ========== STEP 1: Extract PDF to Text ==========
    console.print("[bold cyan]Step 1/4: Extracting PDF text[/bold cyan]\n")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Analyzing PDF...", total=None)
            info = get_pdf_info(pdf_path)

        console.print(f"[green]✓[/green] PDF: [cyan]{pdf_path.name}[/cyan] ({info['pages']} pages)")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Extracting text from {info['pages']} pages...", total=None)
            result = extract_pdf_to_text(pdf_path=pdf_path, output_path=text_file)

        console.print(f"[green]✓[/green] Extracted {result['total_chars']:,} characters using {result['method']}")
        console.print(f"[dim]  → {text_file}[/dim]\n")

    except Exception as e:
        console.print(f"[red]✗ PDF extraction failed: {e}[/red]\n")
        sys.exit(1)

    # ========== STEP 2: Extract Facts ==========
    console.print("[bold cyan]Step 2/4: Extracting facts with LLM[/bold cyan]\n")

    session = Session()
    console.print(f"[green]✓[/green] Session: [cyan]{session.session_id}[/cyan]")
    console.print(f"  Chunk size: {chunk_size} lines, Overlap: {overlap} lines")
    console.print(f"  Workers: {max_workers}, Multipass: {multipass}")

    extractor = FactExtractor(
        chunk_size=chunk_size,
        overlap_size=overlap,
        max_workers=max_workers,
    )

    # Calculate total chunks to provide better progress info
    with open(text_file, "r") as f:
        text = f.read()
    chunks = extractor.chunk_text(text)
    total_chunks = len(chunks)
    total_lines = len(text.split('\n'))

    console.print(f"  Document: {total_lines:,} lines → {total_chunks} chunks\n")

    try:
        # Track running totals
        running_facts = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Processing chunks...", total=total_chunks)

            def update_progress(current, total, message):
                nonlocal running_facts
                # Extract fact count from message
                import re
                match = re.search(r'(\d+) facts validated', message)
                if match:
                    chunk_facts = int(match.group(1))
                    running_facts += chunk_facts
                    desc = f"[cyan]Chunk {current}/{total} • {running_facts} facts extracted"
                else:
                    desc = f"[cyan]{message}"
                progress.update(task, completed=current, description=desc)

            extraction_result = extractor.extract_from_document(
                text_file=text_file,
                document_name=document_name,
                session=session,
                progress_callback=update_progress,
                enable_multipass=multipass,
            )

        console.print(f"\n[green]✓[/green] Extracted {len(extraction_result.facts)} facts ({len(extraction_result.facts)/total_chunks:.1f} facts/chunk avg)")

        # Consolidate facts
        summary = session.load_summary(document_name)
        facts_list = session.load_all_facts(document_name)

        consolidated = {
            "session_id": session.session_id,
            "documents": {
                document_name: {
                    "summary": summary,
                    "facts": facts_list,
                    "fact_count": len(facts_list),
                    "source_text_file": str(text_file),
                }
            },
            "total_facts": len(facts_list),
        }

        import json
        with open(facts_file, "w") as f:
            json.dump(consolidated, f, indent=2)

        console.print(f"[dim]  → {facts_file}[/dim]\n")

    except Exception as e:
        console.print(f"[red]✗ Fact extraction failed: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    # ========== STEP 3: Validate Facts ==========
    if not skip_validation:
        console.print("[bold cyan]Step 3/4: Validating facts[/bold cyan]\n")

        try:
            with console.status("[bold green]Validating facts..."):
                results, stats = validate_consolidated_facts(facts_file, text_file)

            console.print(f"[green]✓[/green] Validated {stats['total_facts']} facts")
            console.print(f"  Valid: {stats['valid_facts']} ({stats['validation_rate']:.1%})")

            if stats.get('near_match_facts', 0) > 0:
                console.print(f"  [yellow]Near Match: {stats['near_match_facts']} ({stats.get('near_match_rate', 0):.1%})[/yellow]")

            if stats['invalid_facts'] > 0:
                console.print(f"  [red]Invalid: {stats['invalid_facts']}[/red]")

            console.print()

        except Exception as e:
            console.print(f"[yellow]⚠ Validation failed: {e}[/yellow]")
            console.print("[dim]Continuing to interactive mode...[/dim]\n")
    else:
        console.print("[bold cyan]Step 3/4: Validation skipped[/bold cyan]\n")

    # ========== STEP 4: Interactive Mode ==========
    if no_interactive:
        console.print("[bold cyan]Step 4/4: Interactive mode skipped[/bold cyan]\n")
        console.print("[green]✅ Processing complete![/green]\n")
        console.print(f"[bold]Output Files:[/bold]")
        console.print(f"  Text: [cyan]{text_file}[/cyan]")
        console.print(f"  Facts: [cyan]{facts_file}[/cyan]")
        console.print(f"\n[dim]To query interactively, run:[/dim]")
        console.print(f"[dim]  frfr interactive {facts_file}[/dim]\n")
        return

    console.print("[bold cyan]Step 4/4: Launching interactive query mode[/bold cyan]\n")
    console.print("[green]✅ Processing complete! Entering interactive mode...[/green]\n")
    console.print("[dim]─" * 60 + "[/dim]\n")

    # Load facts for interactive mode
    import json
    import re
    from frfr.extraction.claude_client import ClaudeClient

    try:
        with open(facts_file, "r") as f:
            data = json.load(f)

        all_facts = []
        document_names = []
        if "documents" in data:
            for doc_name, doc_data in data["documents"].items():
                document_names.append(doc_name)
                all_facts.extend(doc_data.get("facts", []))

        console.print(f"[green]✓[/green] Loaded [cyan]{len(all_facts)}[/cyan] facts")
        if document_names:
            console.print(f"[dim]Documents: {', '.join(document_names)}[/dim]")
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error loading facts: {e}[/red]\n")
        sys.exit(1)

    # Build facts text for queries
    facts_text = ""
    for i, fact in enumerate(all_facts, 1):
        claim = fact.get("claim", "")
        location = fact.get("source_location", "")

        evidence = ""
        if "evidence_quotes" in fact and fact["evidence_quotes"]:
            if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                evidence = fact["evidence_quotes"][0].get("quote", "")
        elif "evidence_quote" in fact:
            evidence = fact.get("evidence_quote", "")

        facts_text += f"{i}. {claim}\n"
        facts_text += f"   Location: {location}\n"
        if evidence:
            evidence_preview = evidence[:150] + "..." if len(evidence) > 150 else evidence
            facts_text += f"   Evidence: \"{evidence_preview}\"\n"
        facts_text += "\n"

    # Initialize Claude
    try:
        claude = ClaudeClient()
    except Exception as e:
        console.print(f"[red]✗ Failed to initialize Claude: {e}[/red]\n")
        sys.exit(1)

    # Show help
    console.print("[bold]Interactive Mode Commands:[/bold]")
    console.print("  [cyan]/stats[/cyan]  - Show database statistics")
    console.print("  [cyan]/help[/cyan]   - Show this help message")
    console.print("  [cyan]exit[/cyan]    - Exit interactive mode")
    console.print()
    console.print("[yellow]Type your questions below:[/yellow]")
    console.print("[dim]─" * 60 + "[/dim]\n")

    # Interactive loop
    while True:
        try:
            question = console.input("[bold cyan]Question:[/bold cyan] ")

            if question.lower() in ['exit', 'quit', 'q']:
                console.print("\n[dim]Goodbye![/dim]\n")
                break

            if not question.strip():
                continue

            # Handle special commands
            if question.startswith('/'):
                cmd = question.lower().strip()

                if cmd == '/stats':
                    console.print()
                    console.print("[bold]Database Statistics:[/bold]")
                    console.print(f"  Total facts: [cyan]{len(all_facts)}[/cyan]")

                    fact_types = {}
                    for fact in all_facts:
                        ft = fact.get("fact_type", "unknown")
                        fact_types[ft] = fact_types.get(ft, 0) + 1

                    console.print("\n  [bold]By Type:[/bold]")
                    for ft, count in sorted(fact_types.items(), key=lambda x: x[1], reverse=True):
                        console.print(f"    {ft}: {count}")

                    qv_count = sum(1 for f in all_facts if f.get("quantitative_values"))
                    console.print(f"\n  Facts with quantitative values: [cyan]{qv_count}[/cyan] ({qv_count/len(all_facts)*100:.1f}%)")
                    console.print()
                    continue

                elif cmd == '/help':
                    console.print()
                    console.print("[bold]Available Commands:[/bold]")
                    console.print("  [cyan]/stats[/cyan]  - Show database statistics")
                    console.print("  [cyan]/help[/cyan]   - Show this help message")
                    console.print("  [cyan]exit[/cyan]    - Exit interactive mode")
                    console.print()
                    continue

                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
                    console.print("[dim]Type /help for available commands[/dim]\n")
                    continue

            # Query with Claude
            console.print()
            with console.status("[bold green]Querying..."):
                prompt = f"""You are answering a question based on extracted facts from a document.

QUESTION: {question}

AVAILABLE FACTS:
{facts_text}

INSTRUCTIONS:
1. Search through the facts to find information relevant to the question
2. Provide a clear, direct answer with INLINE CITATIONS including source locations
3. Cite facts inline using [Fact N, Location] notation immediately after each claim
4. ALWAYS include the source location from the fact (e.g., "Lines 123-125") so the user can cross-check
5. If the facts don't contain enough information to answer, say so clearly
6. Be precise - only claim what the facts actually support

Format your response as:
ANSWER: [your answer with inline citations including locations]
CONFIDENCE: [High/Medium/Low]

SOURCE REFERENCES:
[List each cited fact with its full location for easy cross-checking]

Example format:
ANSWER: Yes, the vendor supports SSO [Fact 42, Lines 1245-1248]. The implementation uses SAML 2.0 protocol [Fact 108, Lines 2103-2105] and integrates with Azure AD [Fact 234, Lines 3567-3569].
CONFIDENCE: High

SOURCE REFERENCES:
- Fact 42 (Lines 1245-1248): SSO configuration details
- Fact 108 (Lines 2103-2105): SAML 2.0 protocol implementation
- Fact 234 (Lines 3567-3569): Azure AD integration
"""
                response = claude.prompt(prompt, max_tokens=4000)

            console.print("[bold]Response:[/bold]")
            console.print(response)
            console.print()

            # Extract and display cited facts
            fact_citations = re.findall(r'\[Fact (\d+)\]', response)
            if fact_citations and show_facts:
                seen = set()
                unique_citations = []
                for num_str in fact_citations:
                    if num_str not in seen:
                        seen.add(num_str)
                        unique_citations.append(num_str)

                console.print("[bold]Cited Facts:[/bold]\n")
                for num_str in unique_citations:
                    try:
                        idx = int(num_str) - 1
                        if 0 <= idx < len(all_facts):
                            fact = all_facts[idx]
                            console.print(f"[cyan]Fact {num_str}:[/cyan] {fact.get('claim', '')}")
                            console.print(f"  [dim]Location: {fact.get('source_location', '')}[/dim]")

                            evidence = ""
                            if "evidence_quotes" in fact and fact["evidence_quotes"]:
                                if isinstance(fact["evidence_quotes"], list) and len(fact["evidence_quotes"]) > 0:
                                    evidence = fact["evidence_quotes"][0].get("quote", "")
                            elif "evidence_quote" in fact:
                                evidence = fact.get("evidence_quote", "")

                            if evidence:
                                evidence_preview = evidence[:200] + "..." if len(evidence) > 200 else evidence
                                console.print(f"  [dim]Evidence: \"{evidence_preview}\"[/dim]")
                            console.print()
                    except (ValueError, IndexError):
                        pass

            console.print("[dim]─" * 60 + "[/dim]\n")

        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye![/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]Goodbye![/dim]\n")
            break
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]\n")


@main.command()
def version():
    """Display version information."""
    console.print("\n[bold]Frfr[/bold] version [cyan]0.1.0[/cyan]")
    console.print("High-confidence document Q&A using LLM swarm consensus\n")


if __name__ == "__main__":
    main()
