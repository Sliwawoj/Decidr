import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bell,
  BellOff,
  Check,
  ChevronRight,
  ExternalLink,
  History,
  LoaderCircle,
  LogOut,
  Mail,
  PenLine,
  Unplug,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
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
  const [signature, setSignature] = useState(s.email_signature);
  const [pushOn, setPushOn] = useState(false);
  const [params] = useSearchParams();

  useEffect(() => {
    setSignature(s.email_signature);
  }, [s.email_signature]);

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
          <p>Powiadomienia, Gmail i podpis w odpowiedziach.</p>
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
              : oauth === "rate_limited"
                ? "Google chwilowo ograniczył zapytania. Poczekaj ok. 15 minut i spróbuj ponownie."
                : "Nie udało się połączyć konta. Sprawdź konfigurację OAuth i spróbuj ponownie."}
        </div>
      )}
      <div className="integrations-grid">
        <Card className="integration-card">
          <div className="integration-top">
            <div className="integration-icon icon-amber">
              <History size={24} />
            </div>
          </div>
          <h2>Historia</h2>
          <p>Zatwierdzone odpowiedzi i zakończone sprawy.</p>
          <Button asChild variant="outline">
            <Link to="/history">
              Otwórz historię
              <ChevronRight size={16} />
            </Link>
          </Button>
        </Card>
        <Card className="integration-card">
          <div className="integration-top">
            <div className="integration-icon icon-blue">
              <Mail size={24} />
            </div>
            <Badge
              className={s.gmail.connected ? "badge-success" : "badge-warning"}
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
          {s.gmail.connected ? (
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
              Połącz konto Gmail
            </Button>
          )}
          <p className="integration-footnote">
            {!s.gmail.configured
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
      <Card className="integration-card signature-card">
        <div className="integration-top">
          <div className="integration-icon icon-green">
            <PenLine size={24} />
          </div>
          <Badge className="badge-neutral">Podpis maila</Badge>
        </div>
        <h2>Podpis w odpowiedziach</h2>
        <p>Dodawany jest na końcu każdej przygotowanej odpowiedzi.</p>
        <Textarea
          value={signature}
          onChange={(event) => setSignature(event.target.value)}
          rows={4}
          className="signature-input"
          maxLength={1000}
        />
        <div className="draft-actions">
          <Button
            variant="outline"
            disabled={busy === "signature" || signature === s.email_signature}
            onClick={() =>
              void run("signature", async () => {
                const saved = await api.saveSettings(signature);
                setSignature(saved.email_signature);
                setNotice("Podpis został zapisany.");
              })
            }
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
      {s.authenticated && (
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
    </div>
  );
}
