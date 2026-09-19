import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronDown,
  ExternalLink,
  FileText,
  LoaderCircle,
  LockKeyhole,
  Mail,
  Save,
  Send,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  ErrorNotice,
  Loading,
  StatusBadge,
  date,
  initials,
  money,
  typeNames,
} from "@/components/common";
import { api } from "@/services/api";
import type { Decision } from "@/types";

export default function DecisionPage({
  refresh,
}: {
  refresh: () => Promise<void>;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [draftText, setDraftText] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirmation, setConfirmation] = useState<Decision | null>(null);
  async function load() {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const d = await api.detail(id);
      setDecision(d);
      setDraftText(d.draft || "");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    setDecision(null);
    setNotice("");
    setConfirmation(null);
    void load();
  }, [id]);
  async function action(operation: () => Promise<Decision>, message?: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await operation();
      setDecision(result);
      setDraftText(result.draft || "");
      if (message) setNotice(message);
      await refresh();
      return result;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function dismiss() {
    if (!decision) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.dismiss(decision);
      await refresh();
      navigate("/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  async function prepareConfirmation() {
    if (!decision) return;
    const saved =
      draftText.trim() === decision.draft
        ? decision
        : await action(() => api.edit(decision, draftText));
    if (saved) setConfirmation(saved);
  }
  async function confirm() {
    if (!confirmation) return;
    const result = await action(() => api.send(confirmation));
    if (result) setConfirmation(null);
    // A failed or timed out send must not offer a blind retry with stale state.
    else {
      setConfirmation(null);
      await refresh();
    }
  }
  if (loading) return <Loading />;
  if (!decision)
    return (
      <ErrorNotice
        message={error || "Nie znaleziono sprawy."}
        retry={() => void load()}
      />
    );
  const d = decision;
  const warnings = [
    ...d.safety_reasons,
    ...d.risk_flags.filter((flag) => !d.safety_reasons.includes(flag)),
  ];
  const done = ["sent", "demo_completed"].includes(d.status);
  const canDismiss =
    ["pending", "draft_ready"].includes(d.status) && !d.send_attempted_at;
  const gmailUrl =
    "https://mail.google.com/mail/u/0/#all/" +
    encodeURIComponent(d.gmail_thread_id);
  const dirty = draftText.trim() !== d.draft;
  return (
    <div className="page-enter">
      <Link className="back-link" to="/">
        <ArrowLeft size={16} />
        Wróć do kolejki
      </Link>
      <div className="page-heading detail-heading">
        <div>
          <div className="section-eyebrow">
            KARTA DECYZJI<span className="dot-separator">/</span>
            {typeNames[d.decision_type].toUpperCase()}
          </div>
          <h1>{d.subject}</h1>
        </div>
        <StatusBadge decision={d} />
      </div>
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      {notice && (
        <div className="notice notice-success" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {warnings.length > 0 && !done && (
        <div className="notice notice-warning" role="status">
          <ShieldCheck size={18} />
          <div>
            <strong>Warto spojrzeć uważniej</strong>
            <ul className="warning-list">
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {done && (
        <div className="completion-banner" role="status">
          <span className="completion-icon">
            <CheckCheck size={25} />
          </span>
          <div>
            <h2>
              {d.is_demo
                ? "Symulacja zakończona. Nic nie wysłaliśmy."
                : "Odpowiedź została wysłana."}
            </h2>
            <p>
              {d.is_demo
                ? "Cały przepływ przetestowany. Twoja odpowiedź pozostała w przestrzeni demo."
                : "Wiadomość jest w oryginalnym wątku Gmaila."}
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/">
              Następna sprawa
              <ArrowRight size={16} />
            </Link>
          </Button>
        </div>
      )}
      <div className="detail-grid">
        <div className="detail-context">
          <Card className="request-card">
            <div className="sender-header">
              <div className="avatar avatar-blue">
                {initials(d.sender_name)}
              </div>
              <div>
                <strong>{d.sender_name}</strong>
                <span>{d.sender_email}</span>
              </div>
              <Mail size={19} />
            </div>
            <div className="received">
              Otrzymano {date(d.received_at, true)} o{" "}
              {new Date(d.received_at).toLocaleTimeString("pl-PL", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <div className="request-body">
              <div className="section-eyebrow">DECYZJA</div>
              <h2>{d.request_text}</h2>
              <p>{d.summary}</p>
            </div>
            <div className="detail-facts">
              {d.amount !== null && (
                <div>
                  <span>Łączna kwota</span>
                  <strong>{money(d.amount, d.currency || "PLN")}</strong>
                </div>
              )}
              {d.deadline && (
                <div>
                  <span>
                    <CalendarDays size={14} />
                    Termin
                  </span>
                  <strong>{date(d.deadline)}</strong>
                </div>
              )}
            </div>
            <div className="analysis-flags">
              <div className="section-eyebrow">FLAGI ANALIZY</div>
              <dl>
                <div>
                  <dt>classification</dt>
                  <dd>
                    <Badge
                      className={
                        d.classification === "needs_reply"
                          ? "badge-success"
                          : "badge-warning"
                      }
                    >
                      {d.classification}
                    </Badge>
                  </dd>
                </div>
                <div>
                  <dt>needs_decision</dt>
                  <dd>{d.needs_decision ? "true" : "false"}</dd>
                </div>
                <div>
                  <dt>is_binary</dt>
                  <dd>{d.is_binary ? "true" : "false"}</dd>
                </div>
                <div>
                  <dt>confidence</dt>
                  <dd>{Math.round(d.confidence * 100)}%</dd>
                </div>
              </dl>
            </div>
            {d.conditions.length > 0 && (
              <div className="conditions">
                <h3>Warunki prośby</h3>
                {d.conditions.map((c, i) => (
                  <p key={i}>
                    <Check size={15} />
                    {c}
                  </p>
                ))}
              </div>
            )}
            <details className="original-message">
              <summary>
                <FileText size={16} />
                Oryginalna wiadomość
                <ChevronDown size={17} />
              </summary>
              <div>{d.original_body}</div>
            </details>
            {!d.is_demo && (
              <a
                className="text-link gmail-link"
                href={gmailUrl}
                target="_blank"
                rel="noreferrer"
              >
                Otwórz w Gmail
                <ExternalLink size={14} />
              </a>
            )}
          </Card>
          <div className="detail-security">
            <ShieldCheck size={17} />
            <span>
              Odpowiedź wyślemy dopiero po Twoim osobnym potwierdzeniu.
            </span>
          </div>
        </div>
        <div className="action-column">
          {d.status === "pending" && d.classification === "needs_reply" ? (
            <Card className="choose-card">
              <div className="step-label">
                <span>01</span>TWÓJ WYBÓR
              </div>
              <h2>Jaką podejmujesz decyzję?</h2>
              <p>
                Przygotujemy krótką odpowiedź. Sprawdzisz i zatwierdzisz ją w
                kolejnym kroku.
              </p>
              <div className="choice-buttons">
                <Button
                  size="lg"
                  disabled={busy}
                  onClick={() => void action(() => api.choose(d, "approve"))}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={21} />
                  ) : (
                    <Check size={21} />
                  )}
                  Zezwól
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  disabled={busy}
                  onClick={() => void action(() => api.choose(d, "reject"))}
                >
                  <X size={21} />
                  Odrzuć
                </Button>
              </div>
              {canDismiss && (
                <button
                  type="button"
                  className="dismiss-action"
                  disabled={busy}
                  onClick={() => void dismiss()}
                >
                  <Trash2 size={14} />
                  Nie odpowiadaj — usuń z kolejki
                </button>
              )}
              <div className="choice-note">
                <LockKeyhole size={15} />
                Ten krok tylko przygotuje draft.
              </div>
            </Card>
          ) : (
            <Card className="draft-card">
              <div className="step-label">
                <span>
                  {done
                    ? "03"
                    : d.classification === "needs_review"
                      ? "01"
                      : "02"}
                </span>
                {done
                  ? "ZAKOŃCZONA SPRAWA"
                  : d.classification === "needs_review"
                    ? "ODPOWIEDŹ DO EDYCJI"
                    : "TWOJA ODPOWIEDŹ"}
              </div>
              <div className="draft-title">
                <h2>
                  {done
                    ? "Zatwierdzona odpowiedź"
                    : d.classification === "needs_review"
                      ? "Sprawdź i dopracuj draft"
                      : "Sprawdź swój draft"}
                </h2>
                {d.user_choice && (
                  <Badge className="badge-neutral">
                    {d.user_choice === "approve" ? "Zezwól" : "Odrzuć"}
                  </Badge>
                )}
                {!d.user_choice && d.classification === "needs_review" && (
                  <Badge className="badge-warning">needs_review</Badge>
                )}
              </div>
              <p>
                {done
                  ? "Treść zaakceptowana w ostatnim kroku."
                  : d.classification === "needs_review"
                    ? "LLM przygotował propozycję odpowiedzi. Możesz ją dowolnie edytować przed wysyłką."
                    : "Możesz zmienić treść, zanim potwierdzisz ostatni krok."}
              </p>
              <div className="draft-recipient">
                <span>Do:</span>
                <strong>{d.sender_email}</strong>
              </div>
              <label htmlFor="draft" className="sr-only">
                Treść odpowiedzi
              </label>
              <Textarea
                id="draft"
                value={draftText}
                onChange={(e) => {
                  setDraftText(e.target.value);
                  setNotice("");
                }}
                maxLength={5000}
                rows={12}
                readOnly={done || !!d.send_attempted_at}
                disabled={busy}
              />
              {!done && !d.send_attempted_at && (
                <>
                  <div className="draft-meta">
                    <span>
                      {dirty ? "Niezapisane zmiany" : "Draft zapisany"}
                      {!dirty && <Check size={12} />}
                    </span>
                    <span>{draftText.length}/5000</span>
                  </div>
                  <div className="draft-actions">
                    <Button
                      variant="outline"
                      disabled={busy || !dirty || !draftText.trim()}
                      onClick={() =>
                        void action(
                          () => api.edit(d, draftText),
                          "Zmiany w drafcie zostały zapisane.",
                        )
                      }
                    >
                      <Save size={16} />
                      Zapisz draft
                    </Button>
                    <Button
                      disabled={busy || !draftText.trim()}
                      onClick={() => void prepareConfirmation()}
                    >
                      {busy ? (
                        <LoaderCircle className="spin" size={16} />
                      ) : (
                        <ArrowRight size={16} />
                      )}
                      Przejdź do potwierdzenia
                    </Button>
                  </div>
                  {canDismiss && (
                    <button
                      type="button"
                      className="dismiss-action"
                      disabled={busy}
                      onClick={() => void dismiss()}
                    >
                      <Trash2 size={14} />
                      Nie odpowiadaj — usuń z kolejki
                    </button>
                  )}
                  <div className="choice-note">
                    <LockKeyhole size={15} />
                    Przed {d.is_demo ? "symulacją" : "wysyłką"} pokażemy pełny
                    podgląd.
                  </div>
                </>
              )}
              {d.send_attempted_at && !done && (
                <ErrorNotice
                  message={
                    d.send_error ||
                    "Wysyłka została rozpoczęta. Odśwież widok i sprawdź Gmail. Nie ponawiamy automatycznie."
                  }
                  retry={() => void load()}
                />
              )}
            </Card>
          )}
        </div>
      </div>
      <Dialog
        open={!!confirmation}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirmation(null);
        }}
      >
        <DialogContent
          onEscapeKeyDown={(e) => {
            if (busy) e.preventDefault();
          }}
          onPointerDownOutside={(e) => {
            if (busy) e.preventDefault();
          }}
        >
          <div className="modal-icon">
            {d.is_demo ? <CheckCheck size={25} /> : <Send size={25} />}
          </div>
          <DialogTitle>
            {d.is_demo
              ? "Potwierdź zakończenie symulacji"
              : "Potwierdź wysłanie odpowiedzi"}
          </DialogTitle>
          <DialogDescription>
            {d.is_demo
              ? "To ostatni krok demo. Żadna wiadomość nie zostanie wysłana."
              : "Wyślemy dokładnie tę treść do wskazanego odbiorcy w oryginalnym wątku Gmaila."}
          </DialogDescription>
          <div className="confirmation-meta">
            <div>
              <span>Odbiorca</span>
              <strong>{confirmation?.sender_email}</strong>
            </div>
            <div>
              <span>Temat</span>
              <strong>Re: {confirmation?.subject}</strong>
            </div>
          </div>
          <pre className="confirmation-preview">{confirmation?.draft}</pre>
          <div className="modal-actions">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirmation(null)}
            >
              Wróć do edycji
            </Button>
            <Button disabled={busy} onClick={() => void confirm()}>
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Check size={17} />
              )}
              {d.is_demo ? "Potwierdzam symulację" : "Potwierdzam i wysyłam"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
