import { useEffect, useState } from "react";
import { Check, LoaderCircle, Send } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DecisionCard, Empty, ErrorNotice } from "@/components/common";
import { StreamToggle, type StreamId } from "@/components/mobile/StreamToggle";
import { TicketCard } from "@/components/mobile/TicketCard";
import { ThumbZone } from "@/components/mobile/ThumbZone";
import { haptic } from "@/lib/haptic";
import { api } from "@/services/api";
import type { Decision } from "@/types";

interface Props {
  decisions: Decision[];
  refresh: () => Promise<void>;
  view: "queue" | "history";
}

function chipsFor(d: Decision): string[] {
  const fromConditions = d.conditions.filter((c) => c.trim().length > 0);
  if (fromConditions.length) return fromConditions.slice(0, 4);
  return d.missing_fields
    .filter(Boolean)
    .slice(0, 4)
    .map((f) => f.replace(/_/g, " "));
}

export default function QueuePage({ decisions, refresh, view }: Props) {
  const [stream, setStream] = useState<StreamId>("quick");
  const [cursor, setCursor] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [selectedChip, setSelectedChip] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Decision | null>(null);

  const pending = decisions.filter((d) => d.status === "pending");
  const drafts = decisions.filter((d) => d.status === "draft_ready");
  const done = decisions.filter((d) =>
    ["sent", "demo_completed"].includes(d.status),
  );

  const streamItems = stream === "quick" ? pending : drafts;
  const safeIndex = streamItems.length
    ? Math.min(cursor, streamItems.length - 1)
    : 0;
  const current = streamItems[safeIndex] ?? null;

  useEffect(() => {
    setCursor(0);
  }, [stream]);

  useEffect(() => {
    if (cursor > 0 && cursor >= streamItems.length) {
      setCursor(Math.max(0, streamItems.length - 1));
    }
  }, [cursor, streamItems.length]);

  useEffect(() => {
    if (!current || current.status !== "draft_ready") {
      setSelectedChip(null);
      return;
    }
    setDraftText(current.draft || "");
    setSelectedChip(null);
  }, [current?.id, current?.version]);

  async function run(op: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await op();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function choose(choice: "approve" | "reject") {
    if (!current) return;
    await run(async () => {
      await api.choose(current, choice);
      setStream("complete");
    });
  }

  async function leave() {
    if (!current) return;
    await run(async () => {
      await api.dismiss(current);
    });
  }

  async function prepareSend() {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      let next = current;
      if (draftText.trim() !== (current.draft || "").trim()) {
        next = await api.edit(current, draftText);
      }
      setConfirmation(next);
      haptic(10);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmSend() {
    if (!confirmation) return;
    setBusy(true);
    setError("");
    try {
      await api.send(confirmation);
      setConfirmation(null);
      await refresh();
      haptic(18);
    } catch (e) {
      setError((e as Error).message);
      setConfirmation(null);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  function applyChip(chip: string) {
    haptic(8);
    setSelectedChip(chip);
    setDraftText((prev) => {
      const base = prev.trim();
      if (!base) return chip;
      if (base.includes(chip)) return base;
      return base + (base.endsWith(".") ? " " : ". ") + chip;
    });
  }

  if (view === "history") {
    return (
      <div className="page-enter queue-page history-page">
        <div className="page-heading">
          <div>
            <h1>Historia</h1>
            <p>Zatwierdzone odpowiedzi w jednym miejscu.</p>
          </div>
        </div>
        {error && <ErrorNotice message={error} />}
        <div className="decision-stack">
          {done.map((d) => (
            <DecisionCard
              key={d.id}
              decision={d}
              onRefresh={async () => {
                setError("");
                try {
                  await refresh();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            />
          ))}
        </div>
        {!done.length && (
          <Empty
            title="Historia dopiero się zaczyna"
            description="Zatwierdzone odpowiedzi pojawią się właśnie tutaj."
          />
        )}
      </div>
    );
  }

  const bothEmpty = pending.length === 0 && drafts.length === 0;

  return (
    <div className="page-enter workspace">
      <h1 className="sr-only">Twoje decyzje</h1>

      <StreamToggle
        value={stream}
        counts={{ quick: pending.length, complete: drafts.length }}
        onChange={setStream}
      />

      {error && <ErrorNotice message={error} />}

      {bothEmpty ? (
        <div className="inbox-zero">
          <div className="inbox-zero-mark" aria-hidden />
          <h2>W kolejce jest spokojnie.</h2>
          <p>Skrzynka odciążona.</p>
        </div>
      ) : !current ? (
        <div className="inbox-zero inbox-zero-soft">
          <h2>
            {stream === "quick"
              ? "Brak spraw Tak/Nie"
              : "Brak szkiców do uzupełnienia"}
          </h2>
          <p>
            {stream === "quick"
              ? "Przełącz na Wybór / Uzupełnij albo poczekaj na synchronizację."
              : "Zezwól lub Odrzuć w strumieniu Szybkie, aby przygotować szkic."}
          </p>
        </div>
      ) : (
        <div className="workspace-stage">
          <div className="workspace-counter">
            <button
              type="button"
              className="workspace-nav"
              disabled={busy || safeIndex <= 0}
              aria-label="Poprzednia sprawa"
              onClick={() => setCursor((c) => Math.max(0, c - 1))}
            >
              ‹
            </button>
            <span className="ticket-mono">
              {String(safeIndex + 1).padStart(2, "0")}
            </span>
            <span>/</span>
            <span className="ticket-mono">
              {String(streamItems.length).padStart(2, "0")}
            </span>
            <button
              type="button"
              className="workspace-nav"
              disabled={busy || safeIndex >= streamItems.length - 1}
              aria-label="Następna sprawa"
              onClick={() =>
                setCursor((c) => Math.min(streamItems.length - 1, c + 1))
              }
            >
              ›
            </button>
          </div>

          <TicketCard
            decision={current}
            chips={stream === "complete" ? chipsFor(current) : undefined}
            selectedChip={selectedChip}
            onChip={applyChip}
            onSwipeStream={(dir) => {
              haptic(8);
              if (dir === "left") setStream("complete");
              else setStream("quick");
            }}
          />

          {stream === "complete" && (
            <div className="workspace-draft">
              <label htmlFor="workspace-draft" className="sr-only">
                Treść odpowiedzi
              </label>
              <Textarea
                id="workspace-draft"
                className="workspace-draft-input"
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                maxLength={5000}
                rows={6}
                disabled={busy}
              />
              <div className="workspace-draft-meta">
                <span>{draftText.length}/5000</span>
                <Link to={"/decisions/" + current.id} className="text-link">
                  Pełny kontekst
                </Link>
              </div>
            </div>
          )}

          <ThumbZone
            mode={stream}
            busy={busy}
            onAllow={() => void choose("approve")}
            onReject={() => void choose("reject")}
            onConfirm={() => void prepareSend()}
            onLeave={() => void leave()}
            confirmLabel={
              current.is_demo ? "Zatwierdź symulację" : "Zatwierdź i wyślij"
            }
          />
        </div>
      )}

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
            {confirmation?.is_demo ? <Check size={25} /> : <Send size={25} />}
          </div>
          <DialogTitle>
            {confirmation?.is_demo
              ? "Potwierdź zakończenie symulacji"
              : "Potwierdź wysłanie odpowiedzi"}
          </DialogTitle>
          <DialogDescription>
            {confirmation?.is_demo
              ? "To ostatni krok demo. Żadna wiadomość nie zostanie wysłana."
              : "Wyślemy dokładnie tę treść w oryginalnym wątku Gmaila."}
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
              Wróć
            </Button>
            <Button disabled={busy} onClick={() => void confirmSend()}>
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Check size={17} />
              )}
              {confirmation?.is_demo
                ? "Potwierdzam symulację"
                : "Potwierdzam i wysyłam"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
