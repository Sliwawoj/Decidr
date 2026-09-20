import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Bell,
  BellOff,
  Check,
  ExternalLink,
  FlaskConical,
  LoaderCircle,
  LogOut,
  Mail,
  RotateCcw,
  Unplug,
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
import { api, request } from "@/services/api";
import {
  isPushSubscribed,
  subscribeToPush,
  unsubscribeFromPush,
} from "@/services/push";
import type { AppStatus } from "@/types";

export default function SettingsPage({
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
  const [pushOn, setPushOn] = useState(false);
  const [params] = useSearchParams();

  useEffect(() => {
    void isPushSubscribed().then(setPushOn);
  }, []);

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
          <div className="section-eyebrow">KONTO I POŁĄCZENIA</div>
          <h1>Ustawienia</h1>
          <p>Powiadomienia i połączenie z Gmailem.</p>
        </div>
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
          {s.gmail.connected && s.mode === "live" ? (
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                void run("gmail-disconnect", async () => {
                  await api.disconnectGmail();
                  setNotice("Konto Gmail zostało rozłączone.");
                })
              }
            >
              {busy === "gmail-disconnect" ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Unplug size={16} />
              )}
              Rozłącz Gmail
            </Button>
          ) : (
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
              Połącz konto Gmail
            </Button>
          )}
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
            <div className="integration-icon icon-amber">
              <Bell size={24} />
            </div>
            <Badge
              className={
                !s.push.configured
                  ? "badge-neutral"
                  : pushOn
                    ? "badge-success"
                    : "badge-neutral"
              }
            >
              {!s.push.configured
                ? "Opcjonalne"
                : pushOn
                  ? "Włączone"
                  : "Wyłączone"}
            </Badge>
          </div>
          <h2>Powiadomienia Web Push</h2>
          <p>
            Krótki sygnał, gdy pojawi się nowa mikrodecyzja. Bez treści maila na
            ekranie blokady.
          </p>
          {pushOn ? (
            <Button
              variant="outline"
              disabled={!!busy || !s.push.configured}
              onClick={() =>
                void run("push-off", async () => {
                  await unsubscribeFromPush();
                  setPushOn(false);
                  setNotice("Powiadomienia są wyłączone na tym urządzeniu.");
                })
              }
            >
              {busy === "push-off" ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <BellOff size={16} />
              )}
              Wyłącz na tym urządzeniu
            </Button>
          ) : (
            <Button
              variant="outline"
              disabled={!!busy || !s.push.configured}
              onClick={() =>
                void run("push", async () => {
                  await subscribeToPush(s.push.public_key!);
                  setPushOn(true);
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
          )}
          <p className="integration-footnote">
            {s.push.configured
              ? "Przeglądarka poprosi o zgodę. Możesz odmówić i nadal używać kolejki."
              : "Brak kluczy VAPID. Kolejka działa bez powiadomień."}
          </p>
        </Card>
      </div>
      {s.mode === "live" && s.authenticated && (
        <Card className="demo-settings">
          <div className="integration-icon icon-blue">
            <LogOut size={24} />
          </div>
          <div>
            <h2>Twoje konto</h2>
            <p>Wyloguj się z tej przeglądarki. Kolejka przestanie być widoczna.</p>
          </div>
          <Button
            variant="outline"
            disabled={!!busy}
            onClick={() =>
              void run("logout", async () => {
                await request("/session", "DELETE");
              })
            }
          >
            {busy === "logout" ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <LogOut size={16} />
            )}
            Wyloguj
          </Button>
        </Card>
      )}
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
