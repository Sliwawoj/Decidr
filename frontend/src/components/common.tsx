import { useState } from "react";
import {
  AlertCircle,
  Check,
  Inbox,
  LoaderCircle,
  Mail,
  MoreHorizontal,
  Pencil,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";
import { Skeleton } from "./ui/skeleton";
import { api } from "@/services/api";
import type { Decision } from "@/types";

export const typeNames: Record<string, string> = {
  purchase: "Zakup",
  invoice: "Faktura",
  schedule: "Termin",
  routine: "Rutynowa prośba",
  other: "Inna sprawa",
};

const CURRENCY_ALIASES: Record<string, string> = {
  ZL: "PLN",
  ZŁ: "PLN",
  PLZ: "PLN",
  "€": "EUR",
  EURO: "EUR",
  $: "USD",
  US$: "USD",
  "£": "GBP",
};

function normalizeCurrency(raw: string | null | undefined): string {
  const cleaned = (raw || "PLN").trim().toUpperCase().replace(/\s+/g, "");
  if (/^[A-Z]{3}$/.test(cleaned)) return cleaned;
  if (CURRENCY_ALIASES[cleaned]) return CURRENCY_ALIASES[cleaned];
  // LLM sometimes glues symbol + amount ("zł80142") — peel a known prefix.
  for (const [alias, code] of Object.entries(CURRENCY_ALIASES)) {
    if (cleaned.startsWith(alias)) return code;
  }
  if (cleaned.startsWith("PLN")) return "PLN";
  return "PLN";
}

export const money = (amount: number, currency = "PLN") => {
  const code = normalizeCurrency(currency);
  try {
    return new Intl.NumberFormat("pl-PL", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ${code}`;
  }
};
export const date = (value: string, full = false) =>
  new Intl.DateTimeFormat("pl-PL", {
    day: "numeric",
    month: full ? "long" : "short",
    ...(full ? { year: "numeric" as const } : {}),
  }).format(new Date(value.length === 10 ? value + "T12:00:00" : value));
export function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
}

export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice notice-error" role="alert">
      <AlertCircle size={19} />
      <div>{message}</div>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          Odśwież
        </Button>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading-stack" aria-label="Ładowanie" role="status">
      <Skeleton className="h-8 w-48" />
      {[1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-40 w-full rounded-2xl" />
      ))}
      <span className="sr-only">Ładowanie danych…</span>
    </div>
  );
}
export function Empty({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Card className="empty-state">
      <div className="empty-icon">
        <Inbox size={28} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
    </Card>
  );
}
export function StatusBadge({ decision: d }: { decision: Decision }) {
  if (d.send_attempted_at && d.status !== "sent")
    return <Badge className="badge-warning">Sprawdź wysyłkę</Badge>;
  if (d.status === "draft_ready")
    return <Badge className="badge-blue">Draft do sprawdzenia</Badge>;
  if (d.status === "sent")
    return (
      <Badge className="badge-success">
        <Check size={12} />
        Wysłano
      </Badge>
    );
  if (d.classification === "needs_review")
    return <Badge className="badge-warning">Wymaga namysłu</Badge>;
  if (d.status === "pending")
    return (
      <Badge className="badge-success">
        <ShieldCheck size={12} />
        Czeka na wybór
      </Badge>
    );
  return <Badge className="badge-neutral">{d.status}</Badge>;
}

export function DecisionCard({
  decision: d,
  onRefresh,
}: {
  decision: Decision;
  onRefresh: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmSend, setConfirmSend] = useState(false);
  const detailPath = "/decisions/" + d.id;
  const isDraft = d.status === "draft_ready" && !d.send_attempted_at;
  const isPending =
    d.status === "pending" && d.classification === "needs_reply";
  const isDone = d.status === "sent";

  async function run(operation: () => Promise<Decision>) {
    setBusy(true);
    setError("");
    try {
      await operation();
      await onRefresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmAndSend() {
    setBusy(true);
    setError("");
    try {
      await api.send(d);
      setConfirmSend(false);
      await onRefresh();
    } catch (e) {
      setError((e as Error).message);
      setConfirmSend(false);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card className="decision-card">
        <div className="decision-top">
          <div
            className={
              "avatar avatar-" +
              (d.decision_type === "purchase" ? "blue" : "sand")
            }
          >
            {initials(d.sender_name)}
          </div>
          <div className="sender">
            <strong>{d.sender_name}</strong>
            <span>{d.sender_email}</span>
          </div>
          <StatusBadge decision={d} />
        </div>
        <Link to={detailPath} className="decision-title-link">
          <h3>{d.subject}</h3>
        </Link>
        <p className="decision-summary">{d.summary}</p>
        <div className="decision-meta">
          <span className="meta-badge">{typeNames[d.decision_type]}</span>
          <span className="meta-badge">{date(d.received_at)}</span>
          {d.deadline && (
            <span className="meta-badge meta-badge-accent">
              Termin: {date(d.deadline)}
            </span>
          )}
          {d.amount !== null && (
            <span className="meta-badge meta-badge-amount">
              {money(d.amount, d.currency || "PLN")}
            </span>
          )}
          {d.status === "draft_ready" && d.user_choice && (
            <span className="meta-badge">
              {d.user_choice === "approve" ? "Zezwól" : "Odrzuć"}
            </span>
          )}
        </div>
        {error && (
          <div className="decision-card-error" role="alert">
            {error}
          </div>
        )}
        <div className="decision-actions">
          {isDraft && (
            <>
              <Button
                size="sm"
                disabled={busy || !d.draft?.trim()}
                onClick={() => setConfirmSend(true)}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Send size={15} />
                )}
                Zatwierdź i wyślij
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => navigate(detailPath)}
              >
                <Pencil size={15} />
                Edytuj draft
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="decision-action-subtle"
                disabled={busy}
                aria-label="Zostaw w mailu"
                title="Zostaw w mailu"
                onClick={() => void run(() => api.dismiss(d))}
              >
                <Mail size={15} />
                <span className="decision-action-label">Zostaw w mailu</span>
              </Button>
            </>
          )}
          {isPending && (
            <>
              <Button
                size="sm"
                disabled={busy}
                onClick={() => void run(() => api.choose(d, "approve"))}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Check size={15} />
                )}
                Zezwól
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void run(() => api.choose(d, "reject"))}
              >
                <X size={15} />
                Odrzuć
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="decision-action-subtle"
                disabled={busy}
                onClick={() => navigate(detailPath)}
              >
                <MoreHorizontal size={15} />
                Więcej / Wymaga namysłu
              </Button>
            </>
          )}
          {!isDraft && !isPending && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(detailPath)}
            >
              {isDone ? "Zobacz sprawę" : "Otwórz sprawę"}
            </Button>
          )}
        </div>
      </Card>
      <Dialog
        open={confirmSend}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirmSend(false);
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
            <Send size={25} />
          </div>
          <DialogTitle>Potwierdź wysłanie odpowiedzi</DialogTitle>
          <DialogDescription>
            Wyślemy dokładnie tę treść do wskazanego odbiorcy w oryginalnym
            wątku Gmaila.
          </DialogDescription>
          <div className="confirmation-meta">
            <div>
              <span>Odbiorca</span>
              <strong>{d.sender_email}</strong>
            </div>
            <div>
              <span>Temat</span>
              <strong>Re: {d.subject}</strong>
            </div>
          </div>
          <pre className="confirmation-preview">{d.draft}</pre>
          <div className="modal-actions">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirmSend(false)}
            >
              Anuluj
            </Button>
            <Button disabled={busy} onClick={() => void confirmAndSend()}>
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Check size={17} />
              )}
              Potwierdzam i wysyłam
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
