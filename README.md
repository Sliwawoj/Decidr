# Decidr

Decidr to lokalna aplikacja, która wyciąga z Gmaila proste decyzje operacyjne, układa je w kolejkę i przygotowuje odpowiedź. **Człowiek zawsze zatwierdza treść i osobno potwierdza wysyłkę** — Decidr nie wysyła maili samodzielnie.

Stack: **React + Vite + TypeScript + Tailwind**, **FastAPI + SQLite**. Jedna skrzynka, jeden użytkownik na bazę. Bez mikroserwisów, Redisa i Celery.

---

## Dla kogo to jest

Firma lub osoba, która:

- dostaje maile typu „czy możemy?”, „potwierdź”, „wybierz opcję”,
- chce szybciej przechodzić proste zgody / odmowy,
- nadal chce **czytać i zatwierdzać** treść odpowiedzi przed wysłaniem.

Nie jest to pełny helpdesk, CRM ani automat odpowiadający za Ciebie.

---

## Jak działa (w skrócie)

```text
Gmail (inbox) → synchronizacja → Gemini (czy to decyzja?) → karta w kolejce
→ Ty wybierasz / edytujesz draft → potwierdzasz wysyłkę → odpowiedź wraca do wątku
```

| Typ sprawy | Co widzisz |
| --- | --- |
| **needs_reply** | Prosta zgoda / odmowa → draft po wyborze |
| **needs_review** | Otwarty draft z miejscem na decyzję (`[WPISZ SWOJĄ DECYZJĘ]`) |
| **skip** | Mail bez decyzji — ukryty w kolejce |

Dodatkowo możesz **odrzucić sprawę z kolejki bez odpowiedzi** (dismiss) albo ustawić **podpis maila** w Ustawieniach.

---

## Szybki start — demo (bez kont i kluczy)

Wymagania: **Docker Desktop / Engine** i Compose **2.24+**.

```sh
docker compose up --build
```

Otwórz **http://localhost:5173**.

- Nie trzeba `.env`, Gmaila ani Gemini.
- Pojawiają się przykładowe sprawy (symulacja — nic nie wychodzi na zewnątrz).
- Reset demo: **Ustawienia → Zresetuj demo**.
- Zatrzymanie: `docker compose down` (dane w wolumenie `decidr-data` zostają).

### Pierwszy przebieg (2–3 min)

1. Wejdź w kolejkę — kilka przykładowych spraw.
2. Otwórz sprawę, kliknij **Zezwól** (lub **Odrzuć**) — powstaje draft.
3. Edytuj treść → **Przejdź do potwierdzenia** → sprawdź podgląd.
4. **Potwierdzam symulację** — sprawa trafia do historii; `sent_at` pozostaje puste.
5. Sprawdź też sprawę „ciężką” (wysoka kwota) — decyzja nadal jest Twoja.

---

## Wdrożenie na żywo (nowa firma / skrzynka)

Poniżej ścieżka od zera do działającej kolejki na prawdziwym Gmailu.

### 1. Co przygotować

| Potrzeba | Po co |
| --- | --- |
| Serwer lub komputer z Dockerem (albo Python 3.12+ i Node 22+) | Host aplikacji |
| Konto Google Cloud | Gmail API + OAuth |
| Klucz **Gemini API** | Klasyfikacja maili i drafty |
| Dedykowana skrzynka testowa (zalecane na start) | Bezpieczne próby |
| (Opcjonalnie) domena / HTTPS / ngrok | Dostęp spoza localhost |
| (Opcjonalnie) klucze VAPID | Powiadomienia w przeglądarce |

### 2. Skopiuj konfigurację

```sh
cp .env.example .env
```

Wygeneruj sekrety (z katalogu repozytorium, z venv lub lokalnym Pythonem):

```powershell
python scripts/generate_secrets.py
python scripts/generate_vapid.py   # tylko jeśli chcesz Web Push
```

Wklej wynik do `.env` i ustaw:

```env
APP_MODE=live
APP_PASSWORD=................        # min. 12 znaków — logowanie do aplikacji
SESSION_SECRET=................      # min. 32 znaki
TOKEN_ENCRYPTION_KEY=................ # klucz Fernet (z generate_secrets)
FRONTEND_URL=http://localhost:5173
GOOGLE_REDIRECT_URI=http://localhost:5173/api/oauth/gmail/callback
COOKIE_SECURE=false                  # true dopiero przy HTTPS
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
EMAIL_SIGNATURE="Z poważaniem,\nImię Nazwisko"
```

Bez `APP_MODE=live` i wymaganych sekretów backend **nie wystartuje** w trybie produkcyjnym.

### 3. Google Cloud — Gmail OAuth

1. Utwórz projekt w [Google Cloud Console](https://console.cloud.google.com/).
2. Włącz **Gmail API**.
3. Skonfiguruj ekran zgody OAuth (tryb testowy + użytkownik testowy = Twoja skrzynka).
4. Utwórz klienta OAuth typu **Web application**.
5. Dodaj **dokładnie** ten Authorized redirect URI (musi być zgodny z `GOOGLE_REDIRECT_URI`):

   `http://localhost:5173/api/oauth/gmail/callback`

6. Skopiuj Client ID i Client Secret do `.env` jako `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

Zakresy używane przez Decidr: `gmail.readonly` + `gmail.send` (bez `gmail.modify` — aplikacja nie oznacza maili jako przeczytane i nie rusza etykiet).

### 4. Uruchomienie

**Docker (zalecane):**

```sh
docker compose up --build
```

**Bez Dockera (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Drugi terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Wejdź na **http://localhost:5173** (ten sam host co w `FRONTEND_URL` — API sprawdza Origin).

### 5. Pierwsze logowanie i połączenie skrzynki

1. Zaloguj się hasłem `APP_PASSWORD`.
2. **Ustawienia → Połącz konto Gmail** → przejdź przez Google OAuth.
3. Ustaw podpis w **Podpis w odpowiedziach** (albo zostaw `EMAIL_SIGNATURE` z `.env`).
4. Poczekaj na automatyczną synchronizację (domyślnie co **30 s**) albo użyj synchronizacji ręcznej, jeśli jest dostępna w UI.
5. Nowe maile od momentu połączenia trafiają do analizy; **historia skrzynki sprzed połączenia nie jest dociągana**.

### 6. Codzienny przepływ użytkownika

1. W kolejce pojawia się karta (nadawca, skrót, kwota/termin gdy wykryte).
2. **Zezwól / Odrzuć** albo edytuj draft w sprawach `needs_review`.
3. Sprawdź treść → potwierdź wysyłkę.
4. Odpowiedź ląduje w oryginalnym wątku Gmail.
5. Niepotrzebną sprawę możesz usunąć z kolejki bez odpowiedzi.

Po restarcie aplikacji podpis zapisany w UI wraca do wartości z `EMAIL_SIGNATURE` / domyślnej — trwały zapis to na razie ustawienie procesowe.

---

## Dostęp spoza localhost (HTTPS / telefon / demo zdalne)

Na samym `http://localhost` OAuth i push na telefonie nie wystarczą. Opcje:

1. Własny reverse proxy z HTTPS, poprawne:
   - `FRONTEND_URL=https://twoja-domena`
   - `GOOGLE_REDIRECT_URI=https://twoja-domena/api/oauth/gmail/callback`
   - ten sam URI w Google Cloud
   - `COOKIE_SECURE=true`
2. Albo szybki tunel (Windows): przy działającym Compose uruchom:

   ```powershell
   .\scripts\ngrok-tunnel.ps1
   ```

   Skrypt wystawia HTTPS na port 5173 i aktualizuje `.env` / backend. W Google Cloud dodaj **nowy** redirect URI z adresem ngrok.

---

## Web Push (opcjonalnie)

1. `python scripts/generate_vapid.py` → `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT=mailto:admin@firma.pl`.
2. Restart backendu / Compose.
3. **Ustawienia → Włącz na tym urządzeniu** (HTTPS lub localhost; czasem wymagana instalacja PWA).

Powiadomienie sygnalizuje nową sprawę — **bez treści maila i bez danych nadawcy**. Odmowa zgody nie blokuje kolejki.

---

## Zmienne środowiskowe

| Zmienna | Opis |
| --- | --- |
| `APP_MODE` | `demo` (domyślnie) lub `live` |
| `APP_PASSWORD` / `SESSION_SECRET` / `TOKEN_ENCRYPTION_KEY` | Wymagane w `live` |
| `FRONTEND_URL` | Origin aplikacji w przeglądarce |
| `GOOGLE_*` | OAuth Gmail |
| `GOOGLE_REDIRECT_URI` | Callback OAuth (musi = Google Console) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Analiza i drafty |
| `GMAIL_QUERY` | Filtr skrzynki (domyślnie `in:inbox -from:me`) |
| `SYNC_INTERVAL_SECONDS` | Interwał schedulera (domyślnie `30`) |
| `EMAIL_SIGNATURE` | Podpis doklejany do draftów |
| `VAPID_*` | Web Push |
| `COOKIE_SECURE` | `true` przy HTTPS |
| `DEMO_AUTOLOAD` | Autoload przykładowych spraw w demo |
| `DATABASE_URL` | SQLite (w Compose: wolumen `/app/data`) |

Szablon: [`.env.example`](.env.example). **Nie commituj `.env`.**

---

## Architektura (dla IT)

Modularny monolit, jeden proces, jedna baza SQLite.

| Obszar | Pliki |
| --- | --- |
| Gate + extract + draft (Gemini) | `backend/app/services/analyzer.py` |
| Sync → analiza → push | `backend/app/services/ingestion.py` |
| Wybór, dismiss, podpis, wysyłka | `backend/app/services/drafts.py` |
| OAuth / MIME / reply | `backend/app/services/gmail.py` |
| VAPID | `backend/app/services/push.py` |
| API | `backend/app/api/routes.py` |
| Scheduler | `backend/app/scheduler.py` |
| UI kolejki / ustawień | `frontend/src/pages/` |

**Stany decyzji:** `pending` → `draft_ready` → `sent` (w demo: `demo_completed`). Pominięte: `skipped`. Usunięte z kolejki bez maila: `dismissed`.

Bezpieczeństwo MVP:

- mutacje wymagają nagłówka `X-Decidr-Client: web` i zgodnego Origin,
- w `live` sesja HttpOnly + hasło z limitem prób,
- `/send` wymaga `confirmed: true` i aktualnej `version`,
- przed wysyłką zapisywane jest `send_attempted_at` — przy timeoucie **nie ma auto-retry** (sprawdź wątek w Gmail).

---

## API (skrót)

`GET /api/health`, `GET /api/status`, `POST|DELETE /api/session`, `PATCH /api/settings`,  
`GET /api/decisions`, `GET /api/decisions/{id}`,  
`POST /api/decisions/{id}/choice`, `POST /api/decisions/{id}/dismiss`,  
`PATCH /api/decisions/{id}/draft`, `POST /api/decisions/{id}/send`,  
`POST /api/gmail/sync`, `DELETE /api/gmail/connection`,  
`POST|DELETE /api/push/subscriptions`,  
`POST /api/oauth/gmail/start`, `GET /api/oauth/gmail/callback`,  
`POST /api/demo/load`, `POST /api/demo/reset`.

---

## Testy (dla deweloperów)

```powershell
# backend
cd backend
..\.venv\Scripts\python.exe -m pytest -q

# frontend
cd frontend
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm test   # wymaga działającego http://localhost:5173
```

CI: `.github/workflows/ci.yml`.

---

## Granice MVP (ważne przed wdrożeniem firmowym)

- **Jedna skrzynka / jeden użytkownik** na bazę; jeden proces backendu.
- To filtr wspomagający, nie gwarancja poprawności LLM ani ochrona przed spoofingiem / prompt injection — **ostateczna decyzja i treść są ludzkie**.
- Brak backfillu historii Gmail, migracji schematu, multi-tenant, polityki retencji i pełnego audytu.
- Treści maili i drafty w SQLite **nie są szyfrowane** (szyfrowane są tokeny OAuth).
- Załączniki nie są analizowane; duże skrzynki wymagają lepszej strategii sync.
- Brak automatycznego ponawiania niepewnej wysyłki.

Na start produkcyjny: osobna skrzynka testowa, HTTPS, własne sekrety, monitorowanie kosztów Gemini i limity Google API.

---

## Dokumentacja zewnętrzna

- [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gmail API — wysyłanie](https://developers.google.com/workspace/gmail/api/guides/sending)
- [Google Cloud OAuth](https://developers.google.com/identity/protocols/oauth2)
