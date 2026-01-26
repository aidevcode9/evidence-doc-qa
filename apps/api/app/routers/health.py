"""Health check endpoint with capabilities info (FR-054, FR-055)."""

from fastapi import APIRouter

from app.config import AUTH_BYPASS_ENABLED, PARSER_PROVIDER

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str | bool | list[str]]:
    """Health check with parser and auth capabilities.

    Returns:
        status: "ok" if healthy
        parser_provider: "pypdf" | "marker" | "llamaparse"
        ocr_supported: True if Marker or LlamaParse (supports scanned PDFs)
        supported_formats: List of supported file extensions
        auth_bypass_enabled: True if auth is bypassed (FOR DEMOS ONLY)
    """
    # Determine supported formats based on parser
    if PARSER_PROVIDER == "pypdf":
        supported_formats = [".pdf"]
        ocr_supported = False
    else:
        # marker and llamaparse support images
        supported_formats = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"]
        ocr_supported = True

    return {
        "status": "ok",
        "parser_provider": PARSER_PROVIDER,
        "ocr_supported": ocr_supported,
        "supported_formats": supported_formats,
        "auth_bypass_enabled": AUTH_BYPASS_ENABLED,
    }
