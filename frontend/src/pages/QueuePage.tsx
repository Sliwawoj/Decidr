import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  Check,
  CheckCheck,
  Clock3,
  FileText,
  Inbox,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DecisionCard, Empty, ErrorNotice } from "@/components/common";
import type { AppStatus, Decision } from "@/types";
import { api } from "@/services/api";

interface Props {
  decisions: Decision[];
  status: AppStatus;
  refresh: () => Promise<void>;
  view: "queue" | "history";
}
export default function QueuePage({ decisions, status, refresh, view }: Props) {
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const pending = decisions.filter((d) => d.status === "pending");
  const drafts = decisions.filter((d) => d.status === "draft_ready");
  const done = decisions.filter((d) =>
    ["sent", "demo_completed"].includes(d.status),
  );
  const visible =
    view === "history"
      ? done
      : filter === "drafts"
        ? drafts
        : filter === "pending"
          ? pending
          : [...drafts, ...pending];
  async function sync() {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      if (status.mode === "live") {
        const result = await api.sync();
        setMessage(
          "Synchronizacja zakończona. Nowe sprawy: " + result.imported + ".",
        );
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-enter">
      <div className="page-heading">
        <div>
          <div className="section-eyebrow">
            {view === "history"
              ? "ZAMKNIĘTE WĄTKI"
              : "TWÓJ DZIEŃ, TROCHĘ PROSTSZY"}
          </div>
          <h1>{view === "history" ? "Historia decyzji" : "Twoje decyzje"}</h1>
          <p>
            {view === "history"
              ? "Twoje wybory i zatwierdzone odpowiedzi w jednym miejscu."
              : "Wiadomości, które czekają na Twoją reakcję."}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={sync}
          disabled={busy || (status.mode === "live" && !status.gmail.connected)}
        >
          <RefreshCw size={16} className={busy ? "spin" : ""} />
          {busy
            ? "Odświeżanie…"
            : status.mode === "demo"
              ? "Odśwież kolejkę"
              : "Synchronizuj Gmail"}
        </Button>
      </div>
      {error && <ErrorNotice message={error} />}
      {message && (
        <div className="notice notice-success" role="status">
          <Check size={18} />
          {message}
        </div>
      )}
      <div className="stats-grid">
        <Card className="stat-card">
          <div className="stat-icon icon-blue">
            <Inbox size={21} />
          </div>
          <div>
            <span>Czeka na Twój wybór</span>
            <strong>{pending.length.toString().padStart(2, "0")}</strong>
          </div>
          <span className="stat-caption">szybka odpowiedź</span>
        </Card>
        <Card className="stat-card">
          <div className="stat-icon icon-amber">
            <FileText size={21} />
          </div>
          <div>
            <span>Drafty do sprawdzenia</span>
            <strong>{drafts.length.toString().padStart(2, "0")}</strong>
          </div>
          <span className="stat-caption">przed potwierdzeniem</span>
        </Card>
        <Card className="stat-card">
          <div className="stat-icon icon-green">
            <CheckCheck size={21} />
          </div>
          <div>
            <span>Zakończone sprawy</span>
            <strong>{done.length.toString().padStart(2, "0")}</strong>
          </div>
          <span className="stat-caption">
            {status.mode === "demo" ? "w symulacji" : "wysłane odpowiedzi"}
          </span>
        </Card>
      </div>
      <div className="queue-layout">
        <div className="queue-column">
          {view === "queue" ? (
            <div className="section-toolbar">
              <div className="tabs" aria-label="Filtruj kolejkę">
                {[
                  ["all", "Do działania", pending.length + drafts.length],
                  ["pending", "Nowe", pending.length],
                  ["drafts", "Drafty", drafts.length],
                ].map(([id, label, count]) => (
                  <button
                    key={id}
                    className={filter === id ? "tab active" : "tab"}
                    aria-pressed={filter === id}
                    onClick={() => setFilter(String(id))}
                  >
                    {label}
                    <span>{count}</span>
                  </button>
                ))}
              </div>
              <span className="sort-label">
                <ArrowDown size={13} />
                Najnowsze
              </span>
            </div>
          ) : (
            <div className="section-toolbar">
              <h2>
                Zakończone{" "}
                <span className="inline-count">{visible.length}</span>
              </h2>
            </div>
          )}
          <div className="decision-stack">
            {visible.map((d) => (
              <DecisionCard key={d.id} decision={d} />
            ))}
          </div>
          {!visible.length && (
            <Empty
              title={
                view === "history"
                  ? "Historia dopiero się zaczyna"
                  : filter === "drafts"
                    ? "Nie masz otwartych draftów"
                    : "W kolejce jest spokojnie"
              }
              description={
                view === "history"
                  ? "Zatwierdzone odpowiedzi pojawią się właśnie tutaj."
                  : filter === "drafts"
                    ? "Wybierz Zezwól lub Odrzuć w sprawie, aby przygotować odpowiedź."
                    : "Nowe sprawy pojawią się tutaj po synchronizacji."
              }
            />
          )}
        </div>
        <aside className="context-rail">
          <Card className="how-card">
            <div className="rail-icon">
              <Sparkles size={21} />
            </div>
            <h2>
              Małe decyzje.
              <br />
              Lżejszy dzień.
            </h2>
            <p>Od prośby do odpowiedzi, bez gubienia kontekstu.</p>
            <ol className="steps">
              <li>
                <span>1</span>
                <div>
                  <strong>Przeczytaj kartę</strong>
                  <p>Prośba, kwota i warunki.</p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <strong>Podejmij decyzję</strong>
                  <p>Zezwól albo odrzuć.</p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <strong>Zatwierdź odpowiedź</strong>
                  <p>Sprawdź draft przed wysyłką.</p>
                </div>
              </li>
            </ol>
            <div className="rail-footnote">
              <ShieldCheck size={16} />
              <span>Nic nie dzieje się bez Ciebie.</span>
            </div>
          </Card>
          <Card className="policy-card">
            <div className="policy-heading">
              <ShieldCheck size={18} />
              <strong>Jak działa kolejka</strong>
              <span className="online-dot" />
            </div>
            <p>
              Gemini ocenia każdy mail. Bez decyzji — pomijamy. Z decyzją —
              krótki opis w powiadomieniu i karta w kolejce.
            </p>
            <Link className="text-link" to="/integrations">
              Zasady i integracje
              <ArrowUpRightIcon />
            </Link>
          </Card>
          <div className="rail-bottom">
            <Clock3 size={15} />
            <span>
              {status.mode === "demo"
                ? "Przykładowe dane · gotowe do testów"
                : status.last_sync_at
                  ? "Ostatnia synchronizacja: " +
                    new Date(status.last_sync_at).toLocaleTimeString("pl-PL", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "Oczekiwanie na synchronizację"}
            </span>
          </div>
          {busy && <LoaderCircle className="spin" size={16} />}
        </aside>
      </div>
    </div>
  );
}
function ArrowUpRightIcon() {
  return <ArrowRight size={14} />;
}
