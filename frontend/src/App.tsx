import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { Check, LoaderCircle, Settings, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Loading } from "@/components/common";
import { api } from "@/services/api";
import type { AppStatus, Decision } from "@/types";
import QueuePage from "@/pages/QueuePage";
import DecisionPage from "@/pages/DecisionPage";
import SettingsPage from "@/pages/SettingsPage";

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const location = useLocation();
  const refresh = useCallback(async () => {
    setError("");
    try {
      const next = await api.status();
      setStatus(next);
      if (next.authenticated) setDecisions(await api.list());
      else setDecisions([]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);
  // Refresh queue as the backend syncs Gmail (~30s); keep the UI lag under one poll.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 10000);
    return () => window.clearInterval(id);
  }, [refresh]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Przejdź do treści
      </a>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-leading">
            <Link
              to="/"
              className="brand topbar-brand"
              aria-label="decidr. — strona główna"
            >
              <span className="brand-symbol">
                D<span />
              </span>
              decidr<span className="brand-period">.</span>
            </Link>
          </div>
          <div className="topbar-actions">
            {status?.authenticated && (
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  "topbar-icon-link" + (isActive ? " active" : "")
                }
                aria-label="Ustawienia"
                title="Ustawienia"
              >
                <Settings size={19} />
              </NavLink>
            )}
          </div>
        </header>
        <main id="main" className="main-content">
          {error && (
            <ErrorNotice message={error} retry={() => void refresh()} />
          )}
          {loading ? (
            <Loading />
          ) : status && !status.authenticated ? (
            <Login onLogin={refresh} />
          ) : (
            status && (
              <Routes>
                <Route
                  path="/"
                  element={
                    <QueuePage
                      decisions={decisions}
                      refresh={refresh}
                      view="queue"
                    />
                  }
                />
                <Route
                  path="/history"
                  element={
                    <QueuePage
                      decisions={decisions}
                      refresh={refresh}
                      view="history"
                    />
                  }
                />
                <Route
                  path="/decisions/:id"
                  element={<DecisionPage refresh={refresh} />}
                />
                <Route
                  path="/settings"
                  element={
                    <SettingsPage status={status} refresh={refresh} />
                  }
                />
                <Route
                  path="/integrations"
                  element={<Navigate to="/settings" replace />}
                />
                <Route
                  path="*"
                  element={
                    <div className="empty-state">
                      <h1>Nie znaleziono strony</h1>
                      <Button asChild>
                        <Link to="/">Wróć do kolejki</Link>
                      </Button>
                    </div>
                  }
                />
              </Routes>
            )
          )}
          {location.pathname !== "/" && (
            <footer className="app-footer">
              <span>
                decidr<span className="brand-period">.</span>
              </span>
              <span>Mniej otwartych wątków. Więcej spokoju.</span>
              <ShieldCheck size={15} />
            </footer>
          )}
        </main>
      </div>
    </div>
  );
}
function Login({ onLogin }: { onLogin: () => Promise<void> }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.login(password);
      await onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="login-card card" onSubmit={submit}>
      <div className="section-eyebrow">TWOJA PRZESTRZEŃ</div>
      <h1>Witaj w Decidr.</h1>
      <p>Zaloguj się, aby zobaczyć sprawy ze swojej skrzynki.</p>
      {error && <ErrorNotice message={error} />}
      <label htmlFor="password">Hasło aplikacji</label>
      <input
        id="password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" disabled={busy}>
        {busy ? (
          <LoaderCircle className="spin" size={17} />
        ) : (
          <Check size={17} />
        )}
        Otwórz przestrzeń
      </Button>
    </form>
  );
}
