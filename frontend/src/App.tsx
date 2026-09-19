import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import {
  ArrowUpRight,
  Bell,
  Check,
  ChevronRight,
  CircleHelp,
  History,
  Inbox,
  Layers3,
  LoaderCircle,
  LogOut,
  Menu,
  Plug2,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorNotice, Loading } from "@/components/common";
import { api, request } from "@/services/api";
import type { AppStatus, Decision } from "@/types";
import QueuePage from "@/pages/QueuePage";
import DecisionPage from "@/pages/DecisionPage";
import IntegrationsPage from "@/pages/IntegrationsPage";

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
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
    setMenu(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);
  // Refresh queue summaries as scheduler imports messages; detail editors keep their own snapshot.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 30000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const pending = decisions.filter((d) =>
    ["pending", "draft_ready"].includes(d.status),
  ).length;
  const nav = [
    { path: "/", label: "Kolejka decyzji", icon: Inbox, count: pending },
    { path: "/history", label: "Historia", icon: History, count: 0 },
    { path: "/integrations", label: "Integracje", icon: Plug2, count: 0 },
  ];
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Przejdź do treści
      </a>
      {menu && (
        <button
          className="mobile-scrim"
          aria-label="Zamknij nawigację"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={"sidebar" + (menu ? " is-open" : "")}>
        <Link to="/" className="brand">
          <span className="brand-symbol">
            D<span />
          </span>
          decidr<span className="brand-period">.</span>
        </Link>
        <div className="workspace">
          <div className="workspace-icon">
            <Layers3 size={18} />
          </div>
          <div>
            <strong>Moja przestrzeń</strong>
            <span>Centrum decyzji</span>
          </div>
          <ChevronRight size={14} />
        </div>
        <div className="nav-label">TWOJA PRACA</div>
        <nav aria-label="Nawigacja główna">
          {nav.map(({ path, label, icon: Icon, count }) => (
            <NavLink
              key={path}
              to={path}
              end
              className={({ isActive }) =>
                "nav-item" + (isActive ? " active" : "")
              }
            >
              <Icon size={19} />
              <span>{label}</span>
              {count > 0 && <span className="nav-count">{count}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="safety-note">
            <ShieldCheck size={22} />
            <strong>Ostatnie słowo należy do Ciebie.</strong>
            <p>Każda odpowiedź wymaga Twojego potwierdzenia.</p>
          </div>
          <Link className="sidebar-help" to="/integrations">
            <CircleHelp size={17} />
            Jak działa Decidr
            <ArrowUpRight size={15} />
          </Link>
          <div className="profile">
            <div className="avatar avatar-navy">
              {status?.mode === "live" ? "JA" : "DE"}
            </div>
            <div>
              <strong>
                {status?.mode === "live"
                  ? "Twoje konto"
                  : "Przestrzeń demonstracyjna"}
              </strong>
              <span>
                {status?.mode === "live"
                  ? "Tryb Gmail"
                  : "Bez prawdziwej wysyłki"}
              </span>
            </div>
            {status?.mode === "live" && status.authenticated && (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Wyloguj"
                onClick={async () => {
                  await request("/session", "DELETE");
                  await refresh();
                }}
              >
                <LogOut size={16} />
              </Button>
            )}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <Button
              className="mobile-menu"
              variant="ghost"
              size="icon"
              aria-label="Otwórz menu"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={20} /> : <Menu size={20} />}
            </Button>
            <span>Moja przestrzeń</span>
            <ChevronRight size={14} />
            <strong>
              {location.pathname.startsWith("/decisions")
                ? "Karta Decyzji"
                : nav.find((n) => n.path === location.pathname)?.label ||
                  "Decidr"}
            </strong>
          </div>
          <div className="topbar-actions">
            {status?.mode === "demo" ? (
              <Badge className="badge-demo">
                <span className="status-dot" />
                Tryb demo
              </Badge>
            ) : (
              status && <Badge className="badge-success">Tryb Gmail</Badge>
            )}
            <Link
              className="notification-link"
              to="/integrations"
              aria-label="Ustawienia powiadomień"
            >
              <Bell size={19} />
            </Link>
          </div>
        </header>
        <main id="main" className="main-content">
          {status?.mode === "demo" && (
            <div className="demo-banner">
              <div>
                <span className="demo-dot" />
                <strong>Bezpieczna przestrzeń do testów.</strong>
                <span>
                  {" "}
                  Dane są przykładowe. Żaden e-mail nie zostanie wysłany.
                </span>
              </div>
              <Link to="/integrations">
                O trybie demo
                <ArrowRightSmall />
              </Link>
            </div>
          )}
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
                      status={status}
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
                      status={status}
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
                  path="/integrations"
                  element={
                    <IntegrationsPage status={status} refresh={refresh} />
                  }
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
          <footer className="app-footer">
            <span>
              decidr<span className="brand-period">.</span>
            </span>
            <span>Mniej otwartych wątków. Więcej spokoju.</span>
            <ShieldCheck size={15} />
          </footer>
        </main>
      </div>
    </div>
  );
}
function ArrowRightSmall() {
  return <ChevronRight size={15} />;
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
