import {
  AlertCircle,
  ArrowRight,
  Check,
  Inbox,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Skeleton } from "./ui/skeleton";
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
  if (d.status === "demo_completed")
    return (
      <Badge className="badge-success">
        <Check size={12} />
        Symulacja zakończona
      </Badge>
    );
  if (d.status === "sent")
    return (
      <Badge className="badge-success">
        <Check size={12} />
        Wysłano
      </Badge>
    );
  if (d.classification === "needs_review")
    return <Badge className="badge-warning">needs_review</Badge>;
  return (
    <Badge className="badge-success">
      <ShieldCheck size={12} />
      needs_reply
    </Badge>
  );
}
export function DecisionCard({ decision: d }: { decision: Decision }) {
  return (
    <Link
      to={"/decisions/" + d.id}
      className="decision-link"
      aria-label={"Otwórz: " + d.subject}
    >
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
            <span>
              {typeNames[d.decision_type]}
              <span className="dot-separator">·</span>
              {date(d.received_at)}
            </span>
          </div>
          <StatusBadge decision={d} />
        </div>
        <h3>{d.subject}</h3>
        <p className="decision-summary">{d.summary}</p>
        <div className="decision-bottom">
          <div className="decision-facts">
            {d.amount !== null && (
              <span className="amount">
                {money(d.amount, d.currency || "PLN")}
              </span>
            )}
            {d.deadline && (
              <span className="deadline">Termin: {date(d.deadline)}</span>
            )}
            {d.status === "draft_ready" && d.user_choice && (
              <span className="deadline">
                Twój wybór: {d.user_choice === "approve" ? "Zezwól" : "Odrzuć"}
              </span>
            )}
            {d.status === "draft_ready" &&
              !d.user_choice &&
              d.classification === "needs_review" && (
                <span className="deadline">Draft do edycji</span>
              )}
          </div>
          <span className="card-action">
            {d.status === "draft_ready" ? "Sprawdź draft" : "Otwórz sprawę"}
            <ArrowRight size={17} />
          </span>
        </div>
      </Card>
    </Link>
  );
}
