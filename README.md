# Decidr

Spokojne miejsce na proste decyzje operacyjne z maila. MVP na hackathon: **React + Vite + TypeScript + Tailwind + shadcn/ui**, **FastAPI + Pydantic + SQLAlchemy + SQLite**.

Decidr przygotowuje kartę i odpowiedź. Użytkownik podejmuje decyzję, edytuje draft i **osobno potwierdza** ostatni krok. Ważne sprawy dostają ostrzeżenie, ale zostają w jednej kolejce szybkiej odpowiedzi.

## Demo — jedno polecenie

Wymagania: Docker Engine/Desktop i Docker Compose **2.24+** (obsługa opcjonalnego pliku env).

```sh
docker compose up --build
```

Otwórz **http://localhost:5173**. Pierwszy start automatycznie tworzy cztery przykładowe sprawy. Nie trzeba tworzyć `.env`, łączyć Gmaila ani podawać klucza LLM/VAPID.

- Frontend: Nginx na porcie 5173, API przez ten sam origin pod `/api`.
- Backend: jeden proces FastAPI, port 8000 dostępny tylko wewnątrz sieci Compose.
- Baza: trwały wolumen `decidr-data`. Restart nie kasuje wyborów.
- Kontenery uruchamiają się w kolejności backend health check → frontend.
- Port aplikacji domyślnie nasłuchuje tylko na localhost.
- Zatrzymanie: `docker compose down`.
- Reset przykładowych spraw: **Integracje → Zresetuj demo**. Usuwa wyłącznie dane demo.

**Demo nigdy nie wywołuje Gmail API ani API modelu.** Wyniki ekstrakcji są oznaczonymi danymi demonstracyjnymi, ale przechodzą ten sam deterministyczny Safety Policy co dane rzeczywiste. Ostatni krok ustawia `demo_completed`, pozostawiając `sent_at = null`. Push może opcjonalnie działać również w demo, jeżeli samodzielnie skonfigurujesz VAPID.

## Scenariusz prezentacji (2–3 minuty)

1. Pokaż kolejkę: cztery przykładowe sprawy do działania. Widoczny bursztynowy pasek oznacza demo.
2. Otwórz **Materiały do warsztatu z klientem**: znana nadawczyni, 249 PLN, termin i warunki.
3. Kliknij **Zezwól**. Powstaje draft; nic nie jest wysyłane.
4. Edytuj odpowiedź. Kliknij **Przejdź do potwierdzenia** — edycja zostanie zapisana.
5. Sprawdź odbiorcę, temat i treść. Możesz wrócić do edycji.
6. Kliknij **Potwierdzam symulację**. Komunikat: „Symulacja zakończona. Nic nie wysłaliśmy.” Sprawa jest w historii.
7. Otwórz umowę za 85 000 PLN — też jest w kolejce do działania; Ty decydujesz.
8. W drugiej sprawie możesz pokazać ścieżkę **Odrzuć**. Integracje pozwalają zresetować demo.

## Uruchamianie bez Dockera

Python 3.12+, Node.js 22+ i npm. Poniżej polecenia PowerShell, uruchamiane w katalogu repozytorium:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip install -e "./backend" --group backend/pyproject.toml:dev
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Jeżeli pip nie obsługuje `--group`, zainstaluj narzędzia testowe: `python -m pip install pytest httpx ruff pyyaml`. Alternatywnie użyj `uv pip install --python .venv/Scripts/python.exe -e ./backend --group backend/pyproject.toml:dev`.

Drugi terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Otwórz **http://localhost:5173**, również gdy Vite wyświetla adres 127.0.0.1. `FRONTEND_URL` oraz adres w przeglądarce muszą być zgodne, bo API sprawdza Origin przy zapisie.

Na Linux/macOS użyj `.venv/bin/python` zamiast `.venv/Scripts/python.exe`. Zależności backendu są przypięte w `requirements.txt`, frontendu w `package-lock.json`.

## Opcjonalny tryb Gmail

To konfiguracja aplikacji, nie wtyczka Gmail do Codex. Nie wpisuj sekretów do kodu ani repozytorium.

1. Skopiuj `.env.example` do `.env`.
2. Wygeneruj własne wartości: `.venv/Scripts/python.exe scripts/generate_secrets.py`. Skopiuj wynik do `.env`:
   - `APP_PASSWORD`: hasło do aplikacji (co najmniej 12 znaków),
   - `SESSION_SECRET`: sekret podpisujący sesję (co najmniej 32 znaki),
   - `TOKEN_ENCRYPTION_KEY`: klucz Fernet szyfrujący tokeny OAuth w SQLite.
3. Ustaw `APP_MODE=live`. Bez wymaganych sekretów backend odmawia startu.
4. W Google Cloud włącz Gmail API. Skonfiguruj ekran zgody OAuth i użytkownika testowego. Utwórz klienta **Web application**.
5. Dodaj dokładny redirect URI: `http://localhost:5173/api/oauth/gmail/callback`.
6. Uzupełnij `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET`.
7. Uzupełnij `GEMINI_API_KEY` (i opcjonalnie `GEMINI_MODEL`).
8. Uruchom ponownie backend/Compose. Zaloguj się hasłem aplikacji i w **Integracje** wybierz **Połącz konto Gmail**.
9. Użyj **Synchronizuj Gmail**. APScheduler wykonuje synchronizację również co 120 sekund.

Zakresy OAuth: `gmail.readonly` i `gmail.send`. Nie żądamy `gmail.modify`: aplikacja nie zmienia flag przeczytania ani etykiet wiadomości. Zapis unikalnego Gmail message ID w bazie po analizie jest punktem oznaczenia sprawy jako przetworzonej.

Synchronizacja pobiera MIME `format=raw`, preferuje `text/plain`, dekoduje znaki, a HTML sprowadza do tekstu. Załączniki nie są analizowane i kierują sprawę do pełnego kontekstu. Warunkiem uproszczenia wiadomości Gmail jest także pozytywny wynik DMARC dla domeny From w nagłówku Authentication-Results wystawionym przez Gmail. To kontrola domeny, nie gwarancja tożsamości konkretnej osoby.

Odpowiedź używa `threadId`, `In-Reply-To`, `References` i zgodnego tematu. Stan OAuth ma 10-minutową ważność, jest jednorazowy i używa PKCE. Tokeny są przechowywane zaszyfrowane; jedna baza obsługuje jedną skrzynkę. Nie zmieniaj klucza szyfrowania bez ponownej autoryzacji konta.

W trybie live każdy nowy mail idzie najpierw do Gemini (czy potrzebna decyzja). Odrzucone wiadomości są pomijane (`skipped`). Przy `needs_decision` drugie wywołanie buduje kartę i krótki `push_text` do powiadomienia.

Jeśli wystawiasz aplikację poza localhost, skonfiguruj HTTPS, poprawny `FRONTEND_URL`, redirect URI i `COOKIE_SECURE=true`. Do demonstracji używaj dedykowanej skrzynki testowej.

## Web Push

1. Wygeneruj parę VAPID: `.venv/Scripts/python.exe scripts/generate_vapid.py`.
2. Skopiuj `VAPID_PUBLIC_KEY` i `VAPID_PRIVATE_KEY` do `.env`, ustaw prawdziwy kontakt `VAPID_SUBJECT=mailto:...` i zrestartuj backend.
3. W przeglądarce wybierz **Integracje → Włącz na tym urządzeniu**.
4. Nowa mikrodecyzja wywołuje Web Push po trwałym zapisie. W demo: po subskrypcji zresetuj przykładowe sprawy.

Wymagany jest HTTPS lub localhost oraz przeglądarka obsługująca Service Worker i Push API. Niektóre przeglądarki mobilne wymagają instalacji witryny na ekranie głównym. Odmowa zgody i błędy push nie wpływają na działanie kolejki. Subskrypcje 404/410 są usuwane. Notification click otwiera Kartę Decyzji. Powiadomienia nie zawierają treści wiadomości ani danych nadawcy. Service Worker nie zapisuje maili i draftów w cache.

## Architektura i pliki do review

Modularny monolit, jedna baza, jeden proces backendu. Bez Celery, Redisa i mikroserwisów.

| Plik | Odpowiedzialność |
| --- | --- |
| `backend/app/services/analyzer.py` | Dwuetapowe Gemini: gate + extract/`push_text` |
| `backend/app/services/ingestion.py` | Analiza → zapis → push |
| `backend/app/services/drafts.py` | Wybór, edycja, kontrola wersji, potwierdzenie, symulacja i atomowe rozpoczęcie wysyłki |
| `backend/app/services/gmail.py` | OAuth, szyfrowane tokeny, MIME, pobieranie i odpowiedź w wątku |
| `backend/app/services/analyzer.py` | Dwuetapowe Gemini: gate + extract/`push_text` |
| `backend/app/services/push.py` | Subskrypcje, VAPID i niezależna od kolejki obsługa błędów |
| `backend/app/db/models.py` | Decyzje, subskrypcje i połączenie Gmail |
| `backend/app/api/routes.py` | Cienkie endpointy i sesja |
| `backend/app/scheduler.py` | APScheduler, jeden job, brak nakładających się uruchomień |
| `frontend/src/pages/DecisionPage.tsx` | Wybór → edycja → utrwalony podgląd → jawne potwierdzenie |
| `frontend/src/components/ui/` | Lokalne komponenty shadcn/ui z Radix i własnym stylem |
| `frontend/public/sw.js` | Powiadomienia bez cache wiadomości |
| `backend/tests/`, `frontend/tests/demo.spec.ts` | Reguły, API, integracje z podstawionymi usługami i demo w przeglądarce |

Przejścia: `analyzed → pending → draft_ready → sent`; pominięte maile: `skipped` (ukryte w API); w demo `draft_ready → demo_completed`. Stan analizowany nie jest publikowany przed zakończeniem filtra.

Filtr MVP: pierwsze wywołanie Gemini decyduje o skip/queue. Drugie buduje kartę i krótki tekst powiadomienia. Ostrzeżenia pochodzą z modelu (`warnings` / `risk_flags`). Finalną treść zatwierdza człowiek.

Każda mutacja wymaga nagłówka `X-Decidr-Client: web`, a przy obecnym Origin jest sprawdzane jego dopasowanie. Tryb live dodatkowo wymaga sesji z ciasteczkiem HttpOnly/SameSite. Hasło ma prosty limit nieudanych prób. Endpoint `/send` wymaga prawdziwego JSON boolean `confirmed: true` i aktualnej `version`, więc zmiana draftu w innej karcie unieważnia stary podgląd.

Przed połączeniem z Gmail zapisywany jest atomowy `send_attempted_at`. Timeout może oznaczać, że Gmail przyjął wiadomość. Nie wykonujemy automatycznej ponownej wysyłki; interfejs wskazuje konieczność sprawdzenia wątku. Zapobiega to duplikatom kosztem ręcznej obsługi niepewnych rezultatów.

## API

`GET /api/health`, `GET /api/status`, `POST|DELETE /api/session`, `GET /api/decisions`, `GET /api/decisions/{id}`, `POST /api/demo/load`, `POST /api/demo/reset`, `POST /api/gmail/sync`, `POST /api/decisions/{id}/choice`, `PATCH /api/decisions/{id}/draft`, `POST /api/decisions/{id}/send`, `POST /api/push/subscriptions`, `POST /api/oauth/gmail/start`, `GET /api/oauth/gmail/callback`.

Przykładowe body:

```json
{ "choice": "approve", "version": 1 }
```
```json
{ "draft": "Dziękuję, potwierdzam.", "version": 2 }
```
```json
{ "confirmed": true, "version": 3 }
```

## Testy

Backend, z folderu `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\ruff.exe check app tests
```

Frontend, z folderu `frontend`:

```sh
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm test
```

Testy przeglądarkowe wymagają działającego demo na **http://localhost:5173** i resetują wyłącznie jego dane demonstracyjne. Możesz testować serwery lokalne albo uruchomiony Compose. Domyślnie używają Chromium; aby wykorzystać zainstalowany Edge na Windows: `$env:PLAYWRIGHT_CHANNEL='msedge'; npm test`. Testy obejmują komputer i viewport telefonu; to emulacja rozmiaru i interakcji, nie test natywnego Safari/iOS. Zrzuty trafiają do ignorowanego folderu `.local`.

Backend sprawdza politykę bezpieczeństwa, duplikaty, stany, konflikty wersji, równoczesne potwierdzenia, kompletne demo i izolację prawdziwych danych. Integracje są testowane z podstawionymi klientami: w testach nie wysyłamy maili, nie wykonujemy płatnych wywołań modelu ani realnych powiadomień.

Workflow `.github/workflows/ci.yml` dodaje testy backendu, typecheck/build, uruchomienie Compose i testy przeglądarkowe w CI.

## Znane granice MVP

- Jedna skrzynka i jeden użytkownik na bazę. Jedna instancja backendu; lokalny scheduler i blokady nie są projektem rozproszonym.
- To konserwatywny filtr, nie gwarancja poprawności ani kompletne zabezpieczenie przed prompt injection lub spoofingiem. Reguły słownikowe mogą zatrzymywać bezpieczne sprawy; nie rozumieją wszystkich wariantów języka. Finalną treść ocenia człowiek.
- Kwoty akceptowane tylko w jednej walucie, bez przeliczania kursów. Data dzienna, bez osobnego stanu upływu godziny; porównanie dat w strefie Europe/Warsaw.
- Synchronizacja od momentu połączenia Gmail (bez backfillu historii), maksymalnie 500 wiadomości na przebieg. Dla małej skrzynki hackathonowej; duże skrzynki wymagają historyId/cursora i lepszego limitowania pracy.
- Załączniki i długie/nieprawidłowe wiadomości wymagają ręcznego sprawdzenia. Nie śledzimy zmian wątku po analizie. Drafty są prostymi szablonami na podstawie zaakceptowanego wyboru.
- Nie ma automatycznego ponawiania niepewnej wysyłki, mechanizmu rozstrzygania jej wyniku, migracji schematu ani wieloużytkownikowego logowania.
- Sekrety OAuth są szyfrowane, treści maili i drafty w SQLite nie. Nie ma jeszcze polityki retencji, backupów ani pełnego audytu.
- Prawdziwe wywołania Gmail, Gemini i Web Push wymagają własnej konfiguracji. Ich obecność w kodzie i testy z podstawionym klientem nie są testem autoryzacji na realnym koncie.
- Docker Compose został przygotowany i statycznie sprawdzony. Na komputerze implementacji nie było Docker Engine/Desktop, więc lokalnie wykonano uruchomienie bez kontenerów; uruchomienie kontenerów pozostaje do weryfikacji na hoście z Dockerem.

## Dokumentacja źródłowa integracji

- [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gmail: wysyłanie wiadomości i odpowiedzi](https://developers.google.com/workspace/gmail/api/guides/sending)
- [shadcn/ui z Vite i Tailwind](https://ui.shadcn.com/docs/installation/vite)
