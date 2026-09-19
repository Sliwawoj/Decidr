import base64
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from types import SimpleNamespace

from app.services.gmail import parse_message, reply_body


def resource(mail):
    return {
        "id": "message1",
        "threadId": "thread1",
        "internalDate": "1789812000000",
        "raw": base64.urlsafe_b64encode(mail.as_bytes()).decode(),
    }


def email():
    mail = EmailMessage()
    mail["From"] = "Anna Kowalska <anna@example.com>"
    mail["To"] = "manager@example.com"
    mail["Message-ID"] = "<original@example.com>"
    mail["Subject"] = "Zakup materiałów"
    return mail


def test_mime_prefers_plain_and_decodes_utf8():
    mail = email()
    mail.set_content("Czy mogę kupić zestaw za 249 PLN?")
    mail.add_alternative("<p>Incorrect HTML amount: 999 PLN</p>", subtype="html")
    parsed = parse_message(resource(mail))
    assert "249 PLN" in parsed.body and "999 PLN" not in parsed.body
    assert parsed.sender_email == "anna@example.com"
    assert parsed.rfc_message_id == "<original@example.com>"


def test_html_normalization_and_attachment():
    mail = email()
    mail.set_content("<script>alert(1)</script><p>Prośba o zakup</p>", subtype="html")
    mail.add_attachment(b"content", maintype="application", subtype="pdf", filename="invoice.pdf")
    parsed = parse_message(resource(mail))
    assert parsed.body == "Prośba o zakup"
    assert parsed.has_attachments


def test_reply_preserves_thread_headers_and_unicode():
    body = reply_body(
        SimpleNamespace(
            sender_email="anna@example.com",
            subject="Zakup materiałów",
            rfc_message_id="<original@example.com>",
            references="<prior@example.com>",
            draft="Dziękuję, potwierdzam.",
            gmail_thread_id="thread1",
        )
    )
    parsed = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(body["raw"]))
    assert body["threadId"] == "thread1"
    assert parsed["In-Reply-To"] == "<original@example.com>"
    assert parsed["References"] == "<prior@example.com> <original@example.com>"
    assert parsed["Subject"] == "Re: Zakup materiałów"
    assert "Dziękuję" in parsed.get_content()


def test_reply_to_mismatch_is_flagged():
    mail = email()
    mail["Reply-To"] = "someoneelse@example.com"
    mail.set_content("Prośba")
    assert parse_message(resource(mail)).normalization_flags


def test_gmail_dmarc_matches_sender_domain():
    mail = email()
    mail["Authentication-Results"] = "mx.google.com; dmarc=pass (p=REJECT) header.from=example.com"
    mail.set_content("Czy mogę kupić zestaw za 249 PLN?")
    assert not parse_message(resource(mail)).normalization_flags


def test_gmail_missing_or_wrong_dmarc_requires_review():
    mail = email()
    mail.set_content("Czy mogę kupić zestaw za 249 PLN?")
    assert any("DMARC" in flag for flag in parse_message(resource(mail)).normalization_flags)
    mail["Authentication-Results"] = "mx.google.com; dmarc=pass header.from=attacker.example"
    assert any("DMARC" in flag for flag in parse_message(resource(mail)).normalization_flags)
