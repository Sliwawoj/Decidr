import { haptic } from "@/lib/haptic";

export type StreamId = "quick" | "complete";

const streams: {
  id: StreamId;
  label: string;
  short: string;
}[] = [
  { id: "quick", label: "Szybkie (Tak/Nie)", short: "Szybkie" },
  { id: "complete", label: "Uzupełnij", short: "Uzupełnij" },
];

export function StreamToggle({
  value,
  counts,
  onChange,
}: {
  value: StreamId;
  counts: Record<StreamId, number>;
  onChange: (next: StreamId) => void;
}) {
  return (
    <div
      className="stream-toggle"
      role="tablist"
      aria-label="Strumień spraw"
    >
      <div
        className={
          "stream-toggle-thumb" +
          (value === "complete" ? " stream-toggle-thumb-right" : "")
        }
        aria-hidden
      />
      {streams.map((s) => {
        const active = value === s.id;
        return (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={"stream-toggle-item" + (active ? " active" : "")}
            onClick={() => {
              if (s.id === value) return;
              haptic(10);
              onChange(s.id);
            }}
          >
            <span className="stream-toggle-label">
              <span className="stream-toggle-full">{s.label}</span>
              <span className="stream-toggle-short">{s.short}</span>
            </span>
            <span className="stream-toggle-count" aria-label={`${counts[s.id]} spraw`}>
              {counts[s.id]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
