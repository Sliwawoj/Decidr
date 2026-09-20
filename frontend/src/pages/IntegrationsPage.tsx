import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Bell,
  BrainCircuit,
  Check,
  ExternalLink,
  FlaskConical,
  LoaderCircle,
  Mail,
  RotateCcw,
  ShieldCheck,
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
  const [reset, setReset] = useState(false);
  const [params] = useSearchParams();
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
