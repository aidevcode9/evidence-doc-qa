import re


_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt",
    r"developer message",
    r"reveal your prompt",
    r"jailbreak",
    r"bypass",
    r"print the hidden rules",
    r"exfiltrate",
]


def is_injection_attempt(question: str) -> bool:
    lower = question.lower()
    return any(re.search(pat, lower) for pat in _INJECTION_PATTERNS)
