"""Conservative rules run AFTER extraction. No rule can promote a rejected email."""

import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.schemas.decision import Analysis, NormalizedMessage


def folded(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.lower().replace("ł", "l"))
        if not unicodedata.combining(c)
    )


SENSITIVE = {
    "Temat prawny lub zobowiązanie umowne": r"\b(umow\w*|kontrakt\w*|prawn\w*|pozew|sadow\w*|legal|contract\w*|lawsuit|nda|aneks\w*)\b",
    "Sprawa personalna lub dane wrażliwe": r"\b(zwolni\w*|zwolnien\w*|wynagrodz\w*|pensj\w*|rekrut\w*|pesel|medycz\w*|chorob\w*|salary|dismiss\w*|hire|hiring|health|password|hasl\w*|poufn\w*|confidential)\b",
    "Decyzja strategiczna": r"\b(strateg\w*|przejec\w*|inwestyc\w*|fuzj\w*|udzial\w*|acquisition|merger|equity)\b",
    "Próba sterowania analizą": r"(ignore (all |previous )?instructions|ignoruj.{0,30}instrukcj|system prompt|classification\s*[:=]|risk_flags)",
}
MONEY = re.compile(r"(?<![\w.,])(-?\d[\d \u00a0.,]*?)\s*(PLN|zł|EUR|USD|GBP|€|\$)", re.IGNORECASE)
CURRENCY_MARKER = re.compile(r"\b(?:PLN|EUR|USD|GBP|CHF|zł|złot\w*|dolar\w*|euro)\b|[€$]", re.IGNORECASE)
BINARY_REQUEST = re.compile(
    r"\bczy\b|\b(can|could|may|do) (you|we|i)\b|prosz[eę] o.{0,30}(zgod|akceptac|zatwierdz|potwierdz)|please (approve|confirm)",
    re.IGNORECASE,
)


def evaluate(
    analysis: Analysis, message: NormalizedMessage, settings: Settings, known_senders: set[str] | None = None
) -> tuple[str, list[str]]:
    reasons = []
    raw_text = message.subject + "\n" + message.body
    text = folded(raw_text)
    if analysis.classification != "microdecision":
        reasons.append("Analiza wymaga pełnego kontekstu")
    if analysis.missing_fields:
        reasons.append("Brak istotnych informacji")
    if analysis.risk_flags:
        reasons.append("Analiza wykryła sygnały ryzyka")
    if analysis.confidence < settings.min_confidence:
        reasons.append("Zbyt niska pewność analizy")
    if message.sender_email.lower() not in (known_senders if known_senders is not None else settings.senders):
        reasons.append("Nieznany nadawca")
    if not BINARY_REQUEST.search(message.body):
        reasons.append("Brak jednoznacznego pytania o zgodę lub odmowę")
    if not analysis.is_binary or analysis.decision_type == "other":
        reasons.append("Sprawa nie jest jednoznaczną decyzją tak/nie")
    if not analysis.summary.strip() or not analysis.request_text.strip() or not message.body.strip():
        reasons.append("Brak czytelnej prośby")
    if message.has_attachments:
        reasons.append("Załącznik wymaga sprawdzenia")
    if message.normalization_flags:
        reasons.extend(message.normalization_flags)
    if not message.rfc_message_id or not message.gmail_thread_id:
        reasons.append("Brak danych bezpiecznej odpowiedzi w wątku")
    for reason, pattern in SENSITIVE.items():
        if re.search(pattern, text):
            reasons.append(reason)

    if analysis.decision_type in {"purchase", "invoice"} and analysis.amount is None:
        reasons.append("Brak kwoty zakupu lub faktury")
    if analysis.amount is not None:
        if analysis.amount > settings.max_amount:
            reasons.append("Kwota przekracza limit")
        if analysis.currency != settings.allowed_currency:
            reasons.append("Waluta poza polityką bezpieczeństwa")

    # Check the ORIGINAL message too: an LLM cannot hide a large amount in its extraction.
    amounts = []
    matches = list(MONEY.finditer(raw_text))
    # Only unambiguous decimal notation is accepted. Thousands written with commas
    # or dots, scientific notation, and prefix currency forms require a human.
    for match in matches:
        numeric = match[1].strip().replace("\u00a0", " ")
        if not re.fullmatch(r"-?\d+(?: \d{3})*(?:[.,]\d{1,2})?", numeric):
            reasons.append("Niejednoznaczny zapis kwoty")
            continue
        amount = float(numeric.replace(" ", "").replace(",", "."))
        currency = {"ZŁ": "PLN", "€": "EUR", "$": "USD"}.get(match[2].upper(), match[2].upper())
        amounts.append((amount, currency))
        if amount < 0 or amount > settings.max_amount:
            reasons.append("Kwota w wiadomości poza dozwolonym limitem")
        if currency != settings.allowed_currency:
            reasons.append("Wiadomość zawiera nieobsługiwaną walutę")
    if len(list(CURRENCY_MARKER.finditer(raw_text))) != len(matches):
        reasons.append("Nieobsługiwany zapis kwoty lub waluty")
    if amounts and (
        analysis.amount is None or any(a != analysis.amount or c != analysis.currency for a, c in amounts)
    ):
        reasons.append("Kwoty w treści wymagają weryfikacji")
    if analysis.amount is not None and not amounts:
        reasons.append("Nie można potwierdzić kwoty w treści")
    if analysis.decision_type == "schedule" and not analysis.deadline:
        reasons.append("Brak jednoznacznego terminu")
    if analysis.deadline:
        try:
            if date.fromisoformat(analysis.deadline) < datetime.now(ZoneInfo("Europe/Warsaw")).date():
                reasons.append("Termin już minął")
        except ValueError:
            reasons.append("Nieprawidłowy lub niejednoznaczny termin")
    return ("review_required" if reasons else "microdecision"), list(dict.fromkeys(reasons))
