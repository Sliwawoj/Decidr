import { useState } from "react";
import { DecisionCard, Empty, ErrorNotice } from "@/components/common";
import type { Decision } from "@/types";

interface Props {
  decisions: Decision[];
  refresh: () => Promise<void>;
  view: "queue" | "history";
}

type QueueTab = "pending" | "drafts";

export default function QueuePage({ decisions, refresh, view }: Props) {
  const [filter, setFilter] = useState<QueueTab>("pending");
  const [error, setError] = useState("");
  const pending = decisions.filter((d) => d.status === "pending");
  const drafts = decisions.filter((d) => d.status === "draft_ready");
  const done = decisions.filter((d) =>
    ["sent", "demo_completed"].includes(d.status),
  );
  const visible =
    view === "history" ? done : filter === "drafts" ? drafts : pending;

  async function handleRefresh() {
    setError("");
    try {
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const tabs: { id: QueueTab; label: string; count: number }[] = [
    { id: "pending", label: "Do decyzji", count: pending.length },
    { id: "drafts", label: "Drafty do zatwierdzenia", count: drafts.length },
  ];

  return (
    <div className="page-enter queue-page">
      <div className="page-heading">
        <div>
          <h1>{view === "history" ? "Historia decyzji" : "Twoje decyzje"}</h1>
          <p>
            {view === "history"
              ? "Twoje wybory i zatwierdzone odpowiedzi w jednym miejscu."
              : "Wiadomości, które czekają na Twoją reakcję."}
          </p>
        </div>
      </div>
      {error && <ErrorNotice message={error} />}
      {view === "queue" && (
        <div className="section-toolbar">
          <div
            className="segmented"
            role="tablist"
            aria-label="Filtruj kolejkę"
          >
            {tabs.map(({ id, label, count }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={filter === id}
                className={
                  filter === id ? "segmented-item active" : "segmented-item"
                }
                onClick={() => setFilter(id)}
              >
                {label}
                <span>{count}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="decision-stack">
        {visible.map((d) => (
          <DecisionCard key={d.id} decision={d} onRefresh={handleRefresh} />
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
  );
}
