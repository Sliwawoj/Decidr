# Weryfikacja implementacji — 2026-09-19

Przeprowadzono lokalnie na Windows, Python 3.12.14, Node.js 24.13.0 i Microsoft Edge.

| Sprawdzenie | Wynik |
| --- | --- |
| Backend `python -m pytest -q` | **65 passed**; 2 ostrzeżenia deprecation z zależności Starlette/httpx |
| Backend `ruff check app tests` | Wszystkie kontrole przeszły |
| Frontend `npm run typecheck` | Bez błędów |
| Frontend `npm run build` | Sukces, Vite 6.4.3; JS 380,89 kB / gzip 120,43 kB |
| Playwright `PLAYWRIGHT_CHANNEL=msedge npm test` | **8 passed**, desktop i emulowany telefon |
| E2E na `npm run preview` | Przepływ approve, edycja, anulowanie podglądu, potwierdzenie, trwałość po reload, reject, blokada ryzyka, reset i błąd API |
| Kontrola wyglądu | Obejrzane zrzuty desktop/mobile kolejki i podglądu odpowiedzi |
| `git diff --check` | Brak błędów |
| Zależności frontendu `npm install` | Audyt: 0 zgłoszonych podatności |
| Compose | YAML, ścieżki build, porty i konfiguracja demo sprawdzone testem; **nie uruchomiono kontenerów — brak Docker Engine/Desktop** |

Backend i produkcyjny podgląd frontendu uruchomiono na 127.0.0.1:8000 i 127.0.0.1:5173. Używaj adresu **http://localhost:5173**, zgodnego z ochroną Origin.

Testy zewnętrznych integracji używają podstawionych klientów. Rzeczywista autoryzacja Google, płatna analiza OpenAI i dostarczenie Web Push nie zostały sprawdzone bez danych dostępowych. Żadna prawdziwa wiadomość nie została wysłana.

Najważniejsze miejsca review: `services/safety.py`, `services/drafts.py`, `services/gmail.py`, `services/ingestion.py`, `frontend/src/pages/DecisionPage.tsx`. Konfiguracja i znane granice MVP są w README.
