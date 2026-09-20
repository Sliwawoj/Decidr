import { useRef } from "react";
import { Link } from "react-router-dom";
import type { Decision } from "@/types";
import { date, money, typeNames } from "@/components/common";

export function TicketCard({
  decision: d,
  chips,
  selectedChip,
  onChip,
  onSwipeStream,
}: {
  decision: Decision;
  chips?: string[];
  selectedChip?: string | null;
  onChip?: (chip: string) => void;
  onSwipeStream?: (dir: "left" | "right") => void;
}) {
  const touchX = useRef(0);

  return (
    <article
      className="ticket"
      onTouchStart={(e) => {
        touchX.current = e.changedTouches[0]?.clientX ?? 0;
      }}
      onTouchEnd={(e) => {
        const x = e.changedTouches[0]?.clientX ?? touchX.current;
        const delta = x - touchX.current;
        if (Math.abs(delta) < 64 || !onSwipeStream) return;
        onSwipeStream(delta < 0 ? "left" : "right");
      }}
    >
      <div className="ticket-rail" aria-hidden />
      <header className="ticket-head">
        <div>
          <p className="ticket-sender">
            {d.sender_name}
            <span className="ticket-sep">·</span>
            <span className="ticket-type">{typeNames[d.decision_type]}</span>
          </p>
          <Link
            to={"/decisions/" + d.id}
            className="ticket-subject"
            aria-label={"Otwórz: " + d.subject}
          >
            {d.subject}
          </Link>
        </div>
        <time className="ticket-stamp" dateTime={d.received_at}>
          {date(d.received_at)}
        </time>
      </header>

      <p className="ticket-essence">{d.request_text || d.summary}</p>
      {d.summary && d.request_text && d.summary !== d.request_text && (
        <p className="ticket-summary">{d.summary}</p>
      )}

      <dl className="ticket-grid">
        {d.amount !== null && (
          <div>
            <dt>Kwota</dt>
            <dd>{money(d.amount, d.currency || "PLN")}</dd>
          </div>
        )}
        {d.deadline && (
          <div>
            <dt>Termin</dt>
            <dd>{date(d.deadline)}</dd>
          </div>
        )}
        <div>
          <dt>Kanał</dt>
          <dd className="ticket-mono-soft">{d.sender_email}</dd>
        </div>
      </dl>

      {chips && chips.length > 0 && (
        <div className="ticket-chips" role="listbox" aria-label="Warianty">
          {chips.map((chip) => (
            <button
              key={chip}
              type="button"
              role="option"
              aria-selected={selectedChip === chip}
              className={
                "ticket-chip" + (selectedChip === chip ? " selected" : "")
              }
              onClick={() => onChip?.(chip)}
            >
              {chip}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
