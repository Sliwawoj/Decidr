from datetime import timedelta

from sqlalchemy import delete

from app.db.models import Decision, utcnow
from app.schemas.decision import Analysis, NormalizedMessage

DEMO_SENDERS = {"anna.kowalska@studio.example", "piotr.nowak@studio.example", "ola@studio.example"}


def fixtures():
    now = utcnow()
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    rows = [
        (
            "purchase",
            "Anna Kowalska",
            "anna.kowalska@studio.example",
            "Materiały do warsztatu z klientem",
            "Cześć! Na jutrzejszy warsztat potrzebujemy zestawu markerów i karteczek. "
            "Łączny koszt brutto z dostawą to 249 PLN. Zakup w ramach budżetu biura. "
            "Czy mogę zamówić ten zestaw? Dzięki, Anna",
            "Zestaw markerów i karteczek na warsztat z klientem.",
            "Czy zatwierdzasz zakup materiałów za 249 PLN?",
            249,
            "PLN",
            tomorrow,
            ["Łączna cena brutto z dostawą", "W ramach budżetu biura"],
            [],
            [],
            "microdecision",
        ),
        (
            "schedule",
            "Piotr Nowak",
            "piotr.nowak@studio.example",
            "Odbiór przesyłki przez kuriera",
            f"Cześć, czy możemy potwierdzić odbiór gotowych materiałów przez kuriera {tomorrow} "
            "w godzinach 10:00–12:00? Przesyłka jest opłacona, bez dodatkowych kosztów. Piotr",
            "Potwierdzenie odbioru gotowych materiałów przez kuriera.",
            f"Czy potwierdzasz odbiór {tomorrow}, 10:00–12:00?",
            None,
            None,
            tomorrow,
            ["Odbiór w godzinach 10:00–12:00", "Bez dodatkowych kosztów"],
            [],
            [],
            "microdecision",
        ),
        (
            "other",
            "Robert Maj",
            "robert@capital-partners.example",
            "Pilne: akceptacja umowy partnerskiej",
            "Proszę dziś zaakceptować umowę inwestycyjną na 85000 PLN. "
            "Umowa obejmuje wyłączność na 3 lata i kary umowne. Czy możemy rozpocząć współpracę?",
            "Umowa inwestycyjna z wyłącznością i wysoką kwotą.",
            "Akceptacja umowy na 85000 PLN.",
            85000,
            "PLN",
            None,
            ["Wyłączność na 3 lata", "Kary umowne"],
            [],
            ["Zobowiązanie prawne"],
            "review_required",
        ),
        (
            "purchase",
            "Ola Wiśniewska",
            "ola@studio.example",
            "Dodatkowy monitor do biura",
            "Cześć, czy mogę kupić dodatkowy monitor do sali projektowej? "
            "Nie wybrałam jeszcze modelu ani dostawcy. Daj znać! Ola",
            "Prośba o monitor bez określonej ceny i modelu.",
            "Czy można kupić monitor?",
            None,
            None,
            None,
            [],
            ["Kwota", "Model i dostawca"],
            [],
            "review_required",
        ),
    ]
    for index, row in enumerate(rows):
        (
            kind,
            name,
            email,
            subject,
            body,
            summary,
            request,
            amount,
            currency,
            deadline,
            conditions,
            missing,
            risks,
            classification,
        ) = row
        message = NormalizedMessage(
            gmail_message_id=f"demo-{index + 1}",
            gmail_thread_id=f"demo-thread-{index + 1}",
            rfc_message_id=f"<demo-{index + 1}@decidr.example>",
            sender_name=name,
            sender_email=email,
            subject=subject,
            received_at=now - timedelta(minutes=12 + index * 19),
            body=body,
        )
        analysis = Analysis(
            classification=classification,
            decision_type=kind,
            sender_name=name,
            summary=summary,
            request_text=request,
            amount=amount,
            currency=currency,
            deadline=deadline,
            conditions=conditions,
            missing_fields=missing,
            risk_flags=risks,
            confidence=0.98 if classification == "microdecision" else 0.65,
            is_binary=classification == "microdecision",
        )
        yield message, analysis


def load_demo(session, ingestion):
    created = 0
    for message, analysis in fixtures():
        _, is_new = ingestion.ingest(session, message, is_demo=True, fixture_analysis=analysis)
        created += int(is_new)
    return created


def reset_demo(session, ingestion):
    session.execute(delete(Decision).where(Decision.is_demo.is_(True)))
    session.commit()
    return load_demo(session, ingestion)
