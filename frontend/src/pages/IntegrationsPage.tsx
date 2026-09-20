import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Bell,
  BrainCircuit,
  Check,
  ExternalLink,
  LoaderCircle,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorNotice } from "@/components/common";
import { api } from "@/services/api";
import { subscribeToPush } from "@/services/push";
import type { AppStatus } from "@/types";

export default function IntegrationsPage({
  status: s,
  refresh,
}: {
  status: AppStatus;
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [signature, setSignature] = useState(s.email_signature);
  const [params] = useSearchParams();

  const saveSignature = async () => {
    setBusy("signature");
    setError("");
    setNotice("");
    try {
      const saved = await api.saveSettings(signature);
      setSignature(saved.email_signature);
      setNotice("Podpis został zapisany.");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  async function run(name: string, fn: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  const oauth = params.get("oauth");
  return (
    <div className="page-enter integrations-page">
      <div className="page-heading">
        <div>
          <div className="section-eyebrow">WSZYSTKO POD KONTROLĄ</div>
          <h1>Integracje i zasady</h1>
          <p>Jasny status połączeń. Bez niespodzianek.</p>
        </div>
        <ShieldCheck size={30} className="muted-icon" />
      </div>
      {error && <ErrorNotice message={error} />}
      {notice && (
        <div className="notice notice-success" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {oauth && (
        <div
          className={
            "notice " +
            (oauth === "connected" ? "notice-success" : "notice-warning")
          }
        >
          {oauth === "connected"
            ? "Konto Gmail zostało połączone."
            : oauth === "cancelled"
              ? "Łączenie konta zostało anulowane."
              : "Nie udało się połączyć konta. Sprawdź konfigurację OAuth i spróbuj ponownie."}
        </div>
      )}
      <div className="integrations-grid">
        <Card className="integration-card">
          <div className="integration-top">
            <div className="integration-icon icon-blue">
              <Mail size={24} />
            </div>
            <Badge
              className={
                s.gmail.connected ? "badge-success" : "badge-warning"
              }
            >
              {s.gmail.connected ? "Połączono" : "Niepołączone"}
            </Badge>
          </div>
          <h2>Gmail</h2>
          <p>
            Prośby trafiają do kolejki, a zatwierdzone odpowiedzi wracają do
            oryginalnego wątku.
          </p>
          {s.gmail.email && <p className="connected-email">{s.gmail.email}</p>}
          <Button
            variant="outline"
            disabled={!!busy || !s.gmail.configured}
            onClick={() =>
              void run("gmail", async () => {
                const { url } = await api.oauth();
                window.location.assign(url);
              })
            }
          >
            {busy === "gmail" ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <ExternalLink size={16} />
            )}
            {s.gmail.connected ? "Połącz ponownie" : "Połącz konto Gmail"}
          </Button>
          <p className="integration-footnote">
            {!s.gmail.configured
              ? "Wymaga danych Google OAuth w konfiguracji serwera."
              : "Tylko odczyt wiadomości i wysyłka po Twoim potwierdzeniu."}
          </p>
        </Card>
        <Card className="integration-card">
          <div className="integration-top">
            <div className="integration-icon icon-purple">
              <BrainCircuit size={24} />
            </div>
            <Badge
              className={s.llm.configured ? "badge-success" : "badge-warning"}
            >
              {s.llm.configured ? "Skonfigurowano" : "Brak klucza"}
            </Badge>
          </div>
          <h2>Analiza AI</h2>
          <p>
            Wydobywa treść prośby, kwotę i warunki. Każda analiza przechodzi
            dodatkowo przez reguły bezpieczeństwa.
          </p>
          <div className="integration-detail">
            <span>Model</span>
            <strong>{s.llm.model}</strong>
          </div>
          <p className="integration-footnote">
            Brak klucza lub błąd AI kieruje sprawę do pełnego kontekstu.
          </p>
        </Card>
        <Card className="integration-card">
          <div className="integration-top">
            <div className="integration-icon icon-amber">
              <Bell size={24} />
            </div>
            <Badge
              className={s.push.configured ? "badge-success" : "badge-neutral"}
            >
              {s.push.configured ? "Skonfigurowano" : "Opcjonalne"}
            </Badge>
          </div>
          <h2>Powiadomienia Web Push</h2>
          <p>
            Krótki sygnał, gdy pojawi się nowa mikrodecyzja. Bez treści maila na
            ekranie blokady.
          </p>
          <Button
            variant="outline"
            disabled={!!busy || !s.push.configured}
            onClick={() =>
              void run("push", async () => {
                await subscribeToPush(s.push.public_key!);
                setNotice("Powiadomienia są włączone na tym urządzeniu.");
              })
            }
          >
            {busy === "push" ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Bell size={16} />
            )}
            Włącz na tym urządzeniu
          </Button>
          <p className="integration-footnote">
            {s.push.configured
              ? "Przeglądarka poprosi o zgodę. Możesz odmówić i nadal używać kolejki."
              : "Brak kluczy VAPID. Kolejka działa bez powiadomień."}
          </p>
        </Card>
      </div>
      <Card className="integration-card" style={{ width: "100%" }}>
        <div className="integration-top">
          <div className="integration-icon icon-green">
            <ShieldCheck size={24} />
          </div>
          <Badge className="badge-neutral">Podpis maila</Badge>
        </div>
        <h2>Podpis w odpowiedziach</h2>
        <p>Dodawany jest na końcu każdej przygotowanej odpowiedzi.</p>
        <textarea
          value={signature}
          onChange={(event) => setSignature(event.target.value)}
          rows={4}
          style={{
            width: "100%",
            resize: "vertical",
            borderRadius: 12,
            border: "1px solid rgba(148, 163, 184, 0.5)",
            padding: "0.75rem 0.9rem",
            background: "rgba(15, 23, 42, 0.02)",
            color: "inherit",
            fontFamily: "inherit",
            marginTop: "0.5rem",
          }}
        />
        <div className="draft-actions" style={{ marginTop: "1rem" }}>
          <Button
            variant="outline"
            disabled={busy === "signature" || signature === s.email_signature}
            onClick={() => void saveSignature()}
          >
            {busy === "signature" ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Check size={16} />
            )}
            Zapisz podpis
          </Button>
        </div>
      </Card>
      <Card className="rules-panel">
        <div>
          <div className="rail-icon">
            <ShieldCheck size={24} />
          </div>
          <h2>
            Proste decyzje.
            <br />
            Konkretne granice.
          </h2>
          <p>
            Gemini ocenia mail w dwóch krokach. Ty zatwierdzasz odpowiedź.
          </p>
        </div>
        <div className="rules-list">
          <div>
            <Check size={18} />
            <span>1. Czy potrzebna decyzja? Jeśli nie — pomijamy</span>
          </div>
          <div>
            <Check size={18} />
            <span>2. Krótki opis decyzji → powiadomienie + kolejka</span>
          </div>
          <div>
            <Check size={18} />
            <span>Wybór → draft → osobne potwierdzenie wysyłki</span>
          </div>
        </div>
      </Card>
      {s.last_sync_error && <ErrorNotice message={s.last_sync_error} />}
    </div>
  );
}
