#!/usr/bin/env python
"""Local parser test script.

Usage:
    # Test with pypdf (digital PDFs only)
    PARSER_PROVIDER=pypdf python scripts/test_parser_local.py path/to/file.pdf

    # Test with marker (OCR support - default)
    PARSER_PROVIDER=marker python scripts/test_parser_local.py path/to/file.pdf
    PARSER_PROVIDER=marker python scripts/test_parser_local.py path/to/image.png

    # Test with llamaparse (requires API key)
    PARSER_PROVIDER=llamaparse LLAMAPARSE_API_KEY=llx-xxx python scripts/test_parser_local.py path/to/file.pdf
"""

import asyncio
import sys
import time
from pathlib import Path

# Add apps/api to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_parser_local.py <file_path>")
        print("\nExamples:")
        print("  PARSER_PROVIDER=pypdf python scripts/test_parser_local.py doc.pdf")
        print("  PARSER_PROVIDER=marker python scripts/test_parser_local.py doc.pdf")
        print("  PARSER_PROVIDER=marker python scripts/test_parser_local.py image.png")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    # Import after path setup
    from app.config import PARSER_PROVIDER
    from app.parsers import get_parser_client

    print(f"=" * 60)
    print(f"Parser Test")
    print(f"=" * 60)
    print(f"File: {file_path}")
    print(f"Provider: {PARSER_PROVIDER}")

    # Get parser
    try:
        parser = get_parser_client()
        print(f"Parser class: {parser.__class__.__name__}")
        print(f"Supported extensions: {', '.join(sorted(parser.supported_extensions))}")
    except Exception as e:
        print(f"Error creating parser: {e}")
        sys.exit(1)

    # Check extension
    ext = Path(file_path).suffix.lower().lstrip(".")
    if ext not in parser.supported_extensions:
        print(f"\nError: Extension '{ext}' not supported by {PARSER_PROVIDER}")
        print(f"Supported: {', '.join(sorted(parser.supported_extensions))}")
        sys.exit(1)

    # Parse
    print(f"\n{'=' * 60}")
    print("Parsing...")
    print(f"{'=' * 60}")

    start = time.perf_counter()
    try:
        result = await parser.parse(file_path)
    except Exception as e:
        print(f"Error parsing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Results
    print(f"\n{'=' * 60}")
    print("Results")
    print(f"{'=' * 60}")
    print(f"Provider: {result.provider}")
    print(f"Parse time: {elapsed_ms}ms (reported: {result.parse_time_ms}ms)")
    print(f"Cached: {result.cached}")
    print(f"Pages: {len(result.pages)}")
    print(f"Tables: {len(result.tables)}")
    print(f"Metadata: {result.metadata}")
    print(f"Total text length: {len(result.text)} chars")

    # Per-page summary
    print(f"\n{'=' * 60}")
    print("Per-Page Summary")
    print(f"{'=' * 60}")
    for page in result.pages:
        text_preview = page.text[:100].replace("\n", " ") if page.text else "(empty)"
        print(f"  Page {page.page_number}: {len(page.text)} chars, "
              f"offset {page.char_start}-{page.char_end}")
        print(f"    Preview: {text_preview}...")

    # Full text preview
    print(f"\n{'=' * 60}")
    print("Full Text Preview (first 500 chars)")
    print(f"{'=' * 60}")
    print(result.text[:500] if result.text else "(no text extracted)")

    # Warnings
    if len(result.text) < 10:
        print(f"\n{'=' * 60}")
        print("WARNING: Very little text extracted!")
        print(f"{'=' * 60}")
        print("This may indicate:")
        print("  - Scanned/image-based PDF that needs OCR")
        print("  - Empty document")
        print("  - Parser issue")
        if PARSER_PROVIDER == "pypdf":
            print("\nTry: PARSER_PROVIDER=marker to enable OCR")


if __name__ == "__main__":
    asyncio.run(main())
