import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset", {
    headers: { "X-Decidr-Client": "web" },
  });
  expect(response.ok()).toBeTruthy();
});

test("approve, edit, preview, cancel, confirm and persist demo", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("Tryb demo", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("tab", { name: /Szybkie/ }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Pełny kontekst" })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: "../.local/queue-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Otwórz: Materiały do warsztatu z klientem" })
    .click();
  await page.getByRole("button", { name: "Zezwól", exact: true }).click();
  await expect(page.getByLabel("Treść odpowiedzi")).toContainText(
    "Wyrażam zgodę",
  );
  const edited = "Dziękuję, zatwierdzam zakup za 249 PLN brutto z dostawą.";
  await page.getByLabel("Treść odpowiedzi").fill(edited);
  await page.getByRole("button", { name: "Przejdź do potwierdzenia" }).click();
  await expect(page.getByRole("dialog")).toContainText(edited);
  await expect(page.getByRole("dialog")).toContainText(
    "anna.kowalska@studio.example",
  );
  await page.screenshot({
    path: "../.local/confirmation-" + testInfo.project.name + ".png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Wróć do edycji" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Przejdź do potwierdzenia" }).click();
  await page.getByRole("button", { name: "Potwierdzam symulację" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Symulacja zakończona. Nic nie wysłaliśmy.",
    }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Treść odpowiedzi")).toHaveValue(edited);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("high-stakes matter stays actionable with warning, reject creates a draft", async ({
  page,
  request,
}) => {
  await page.goto("/history");
  await expect(page.getByText("Historia dopiero się zaczyna")).toBeVisible();
  const list = await request.get("/api/decisions");
  const decisions = (await list.json()) as { id: string; subject: string }[];
  const highStakes = decisions.find((d) =>
    d.subject.includes("akceptacja umowy"),
  );
  const courier = decisions.find((d) => d.subject.includes("Odbiór przesyłki"));
  expect(highStakes && courier).toBeTruthy();
  await page.goto("/decisions/" + highStakes!.id);
  await expect(page.getByText("Warto spojrzeć uważniej")).toBeVisible();
  await expect(page.getByRole("button", { name: "Zezwól", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Odrzuć", exact: true })).toBeVisible();
  await page.getByText("Oryginalna wiadomość", { exact: true }).click();
  await expect(
    page.getByText(/Proszę dziś zaakceptować umowę inwestycyjną/),
  ).toBeVisible();
  await page.goto("/decisions/" + courier!.id);
  await page.getByRole("button", { name: "Odrzuć", exact: true }).click();
  await expect(page.getByLabel("Treść odpowiedzi")).toContainText(
    "Nie wyrażam zgody",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sprawdź swój draft" }),
  ).toBeVisible();
});

test("settings status and reset work without secrets", async ({ page }) => {
  await page.goto("/settings");
  await expect(
    page.getByRole("button", { name: "Połącz konto Gmail" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Włącz na tym urządzeniu" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Zresetuj demo" }).click();
  await page
    .getByRole("button", { name: "Przywróć demo", exact: true })
    .click();
  await expect(
    page.getByText("Demo gotowe do nowego przebiegu."),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect
    .poll(() =>
      page.evaluate(
        async () => !!(await navigator.serviceWorker.getRegistration()),
      ),
    )
    .toBeTruthy();
});

test("API failure has a recoverable error state", async ({ page }) => {
  await page.route("**/api/decisions", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Test: serwer chwilowo niedostępny" }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Test: serwer chwilowo niedostępny",
  );
  await page.unroute("**/api/decisions");
  await page.getByRole("button", { name: "Odśwież", exact: true }).click();
  await expect(
    page.getByRole("link", {
      name: "Otwórz: Materiały do warsztatu z klientem",
    }),
  ).toBeVisible();
});

test("queue shows one ticket and stream toggle", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("tab", { name: /Szybkie/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("link", {
      name: "Otwórz: Materiały do warsztatu z klientem",
    }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Zezwól", exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Odrzuć", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: /Wybór/ }).click();
  await expect(
    page.getByText(/Brak szkiców|Szkic|Zatwierdź/i).first(),
  ).toBeVisible();
});
