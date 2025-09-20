import re
from dataclasses import dataclass, asdict
from typing import Dict, Tuple

# --- Regexes (simple, demo-friendly; you can harden later) ---
EMAIL_RE        = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE        = re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\d[ -]?){9,12}(?!\d)")
AADHAAR_RE      = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
CREDITCARD_RE   = re.compile(r"(?:\b(?:\d[ -]*?){13,19}\b)")
APIKEY_HINT_RE  = re.compile(r"\b(api[_-]?key|secret[_-]?key|token)\b", re.IGNORECASE)

SENSITIVE_KEYWORDS = [
    "password", "passwd", "secret", "credential", "otp",
    "api key", "secret key", "access token", "bearer",
    "ssn", "aadhaar", "pan number", "credit card", "cvv",
]

@dataclass
class SafeguardReport:
    safe_mode: bool
    max_chars: int
    truncated: bool
    redactions: Dict[str, int]
    flags: Dict[str, int]

def _count(pattern: re.Pattern, text: str) -> int:
    return len(pattern.findall(text))

def scan_text(text: str) -> Dict[str, int]:
    """Return counts of possible PII/sensitive markers in text."""
    flags = {
        "email": _count(EMAIL_RE, text),
        "phone": _count(PHONE_RE, text),
        "aadhaar": _count(AADHAAR_RE, text),
        "creditcard": _count(CREDITCARD_RE, text),
        "apikey_hint": _count(APIKEY_HINT_RE, text),
        "keywords": sum(1 for k in SENSITIVE_KEYWORDS if k.lower() in text.lower()),
    }
    return flags

def _redact(pattern: re.Pattern, text: str, token: str) -> Tuple[str, int]:
    count = 0
    def repl(_):
        nonlocal count
        count += 1
        return token
    return pattern.sub(repl, text), count

def redact_pii(text: str) -> Tuple[str, Dict[str, int]]:
    redactions = {}
    text, n_email      = _redact(EMAIL_RE, text, "[EMAIL]")
    text, n_phone      = _redact(PHONE_RE, text, "[PHONE]")
    text, n_aadhaar    = _redact(AADHAAR_RE, text, "[AADHAAR]")
    text, n_cc         = _redact(CREDITCARD_RE, text, "[CARD]")
    text, n_apikey     = _redact(APIKEY_HINT_RE, text, "[SECRET]")
    redactions.update({
        "email": n_email,
        "phone": n_phone,
        "aadhaar": n_aadhaar,
        "creditcard": n_cc,
        "apikey_hint": n_apikey,
    })
    return text, redactions

def apply_safeguards(text: str, *, safe_mode: bool = True, max_chars: int = 600) -> Tuple[str, SafeguardReport]:
    original = text
    redactions = {"email":0,"phone":0,"aadhaar":0,"creditcard":0,"apikey_hint":0}
    if safe_mode:
        text, redactions = redact_pii(text)
        # length cap (char-based, simple and fast)
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars].rstrip() + "…"
    else:
        truncated = False

    flags = scan_text(original)
    report = SafeguardReport(
        safe_mode=safe_mode,
        max_chars=max_chars,
        truncated=truncated,
        redactions=redactions,
        flags=flags,
    )
    return text, report

def report_dict(report: SafeguardReport) -> Dict:
    return asdict(report)
