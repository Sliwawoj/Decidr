import { LoaderCircle } from "lucide-react";
import { haptic } from "@/lib/haptic";

export function ThumbZone({
  mode,
  busy,
  onAllow,
  onReject,
  onConfirm,
  onLeave,
  confirmLabel = "Zatwierdź i wyślij",
}: {
  mode: "quick" | "complete";
  busy: boolean;
  onAllow?: () => void;
  onReject?: () => void;
  onConfirm?: () => void;
  onLeave: () => void;
  confirmLabel?: string;
}) {
  function press(fn?: () => void) {
    if (!fn || busy) return;
    haptic(14);
    fn();
  }

  return (
    <div className="thumb-zone">
      {mode === "quick" ? (
        <div className="thumb-pair">
          <button
            type="button"
            className="tactile-btn tactile-reject"
            disabled={busy}
            onClick={() => press(onReject)}
          >
            {busy ? <LoaderCircle className="spin" size={18} /> : null}
            Odrzuć
          </button>
          <button
            type="button"
            className="tactile-btn tactile-allow"
            disabled={busy}
            onClick={() => press(onAllow)}
          >
            {busy ? <LoaderCircle className="spin" size={18} /> : null}
            Zezwól
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="tactile-btn tactile-confirm"
          disabled={busy}
          onClick={() => press(onConfirm)}
        >
          {busy ? <LoaderCircle className="spin" size={18} /> : null}
          {confirmLabel}
        </button>
      )}
      <button
        type="button"
        className="tactile-escape"
        disabled={busy}
        onClick={() => press(onLeave)}
      >
        {mode === "quick"
          ? "Wymaga namysłu / Zostaw w mailu"
          : "Zostaw w mailu"}
      </button>
    </div>
  );
}
