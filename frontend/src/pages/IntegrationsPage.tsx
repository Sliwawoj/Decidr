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
import { ErrorNotice, money } from "@/components/common";
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
                s.mode === "demo"
                  ? "badge-neutral"
                  : s.gmail.connected
                    ? "badge-success"
                    : "badge-warning"
              }
            >
              {s.mode === "demo"
                ? "Wyłączone w demo"
                : s.gmail.connected
                  ? "Połączono"
                  : "Niepołączone"}
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
            disabled={!!busy || s.mode === "demo" || !s.gmail.configured}
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
            {s.mode === "demo"
              ? "Przełącz APP_MODE na live w konfiguracji, aby używać własnej skrzynki."
              : !s.gmail.configured
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
              className={
                s.mode === "demo"
                  ? "badge-neutral"
                  : s.llm.configured
                    ? "badge-success"
                    : "badge-warning"
              }
            >
              {s.mode === "demo"
                ? "Analizy przykładowe"
                : s.llm.configured
                  ? "Skonfigurowano"
                  : "Brak klucza"}
            </Badge>
          </div>
          <h2>Analiza AI</h2>
          <p>
            Wydobywa treść prośby, kwotę i warunki. Każda analiza przechodzi
            dodatkowo przez reguły bezpieczeństwa.
          </p>
          <div className="integration-detail">
            <span>{s.mode === "demo" ? "Tryb analizy" : "Model"}</span>
            <strong>
              {s.mode === "demo" ? "Stałe dane demonstracyjne" : s.llm.model}
            </strong>
          </div>
          <p className="integration-footnote">
            {s.mode === "demo"
              ? "Demo nie wykonuje połączeń z API modelu."
              : "Brak klucza lub błąd AI kieruje sprawę do pełnego kontekstu."}
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
            AI porządkuje prośbę. Filtr bezpieczeństwa może ją zatrzymać.
            Decyzja zawsze należy do Ciebie.
          </p>
        </div>
        <div className="rules-list">
          <div>
            <Check size={18} />
            <span>Tylko znani nadawcy i jednoznaczne prośby</span>
          </div>
          <div>
            <Check size={18} />
            <span>
              Limit kwoty:{" "}
              <strong>{money(s.policy.max_amount, s.policy.currency)}</strong>
            </span>
          </div>
          <div>
            <Check size={18} />
            <span>
              Minimalna pewność analizy:{" "}
              <strong>{Math.round(s.policy.min_confidence * 100)}%</strong>
            </span>
          </div>
          <div>
            <ShieldCheck size={18} />
            <span>
              Tematy prawne, personalne i strategiczne wymagają pełnego
              kontekstu
            </span>
          </div>
          <div>
            <Check size={18} />
            <span>Wybór → draft → edycja → osobne potwierdzenie</span>
          </div>
        </div>
      </Card>
      {s.last_sync_error && <ErrorNotice message={s.last_sync_error} />}
      {s.mode === "demo" && (
        <Card className="demo-settings">
          <div className="integration-icon icon-amber">
            <FlaskConical size={24} />
          </div>
          <div>
            <h2>Zacznij demonstrację od nowa</h2>
            <p>
              Przywróć cztery przykładowe sprawy i wyczyść wybory oraz drafty
              demo.
            </p>
          </div>
          <Button variant="outline" onClick={() => setReset(true)}>
            <RotateCcw size={16} />
            Zresetuj demo
          </Button>
        </Card>
      )}
      <Dialog open={reset} onOpenChange={setReset}>
        <DialogContent>
          <DialogTitle>Przywrócić przykładowe sprawy?</DialogTitle>
          <DialogDescription>
            Wybory i drafty z bieżącej symulacji zostaną usunięte. W kolejce
            pojawią się cztery początkowe wiadomości demo.
          </DialogDescription>
          <div className="modal-actions">
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => setReset(false)}
            >
              Anuluj
            </Button>
            <Button
              disabled={!!busy}
              onClick={() =>
                void run("reset", async () => {
                  await api.reset();
                  setReset(false);
                  setNotice("Demo gotowe do nowego przebiegu.");
                })
              }
            >
              {busy === "reset" && <LoaderCircle size={16} className="spin" />}
              Przywróć demo
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
