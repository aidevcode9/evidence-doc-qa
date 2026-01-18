import re
import unicodedata


_INJECTION_PATTERNS = [
    r"ignore\s*(previous|prior|all|the|your)?\s*instructions?",
    r"system\s*prompt",
    r"developer\s*message",
    r"reveal\s*(your|the)?\s*prompt",
    r"jailbreak",
    r"bypass\s*(the|your|all)?\s*(rules?|filters?|restrictions?|safety)?",
    r"print\s*(the)?\s*hidden\s*rules?",
    r"exfiltrate",
    r"disregard\s*(previous|prior|all|the|your)?\s*(instructions?|rules?)?",
    r"override\s*(the|your|all)?\s*(instructions?|rules?|system)?",
    r"new\s*instructions?\s*:?",
    r"forget\s*(everything|all|previous|prior)",
    r"act\s*as\s*(if|a|an)",
    r"pretend\s*(you|to\s*be)",
    r"you\s*are\s*now\s*(a|an|in)",
    r"roleplay\s*as",
]


def _normalize_text(text: str) -> str:
    """Normalize unicode and whitespace to catch homoglyph attacks."""
    # NFKC normalization converts lookalike chars to ASCII equivalents
    normalized = unicodedata.normalize("NFKC", text)
    # Replace common homoglyphs that survive NFKC
    homoglyph_map = {
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "ｉ": "i", "ｌ": "l", "ｏ": "o", "ｅ": "e", "ａ": "a",
        "ｓ": "s", "ｔ": "t", "ｎ": "n", "ｒ": "r", "ｕ": "u",
        "І": "I", "О": "O", "Ε": "E", "Α": "A", "Ρ": "P",  # Cyrillic/Greek
        "і": "i", "о": "o", "е": "e", "а": "a", "р": "p",
    }
    for char, replacement in homoglyph_map.items():
        normalized = normalized.replace(char, replacement)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower()


def is_injection_attempt(question: str) -> bool:
    """Check if question contains injection patterns."""
    normalized = _normalize_text(question)
    return any(re.search(pat, normalized) for pat in _INJECTION_PATTERNS)
