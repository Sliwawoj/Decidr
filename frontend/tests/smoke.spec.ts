import { test, expect } from "@playwright/test";

test("queue workspace and decision flow work in live mode", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Twoje decyzje" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Szybkie/ })).toBeVisible();
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
  await page.getByRole("button", { name: "Potwierdzam i wysyłam" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Odpowiedź została wysłana.",
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
}) => {
  await page.goto("/history");
  await expect(page.getByText("Historia dopiero się zaczyna")).toBeVisible();
  await page.goto("/");
  await page
    .getByRole("link", { name: /Pilne: akceptacja umowy partnerskiej/ })
    .click();
  await expect(page.getByText("Warto spojrzeć uważniej")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Zezwól", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Odrzuć", exact: true }),
  ).toBeVisible();
  await page.getByText("Oryginalna wiadomość", { exact: true }).click();
  await expect(
    page.getByText(/Proszę dziś zaakceptować umowę inwestycyjną/),
  ).toBeVisible();
  await page.goto("/");
  await page
    .getByRole("link", { name: "Otwórz: Odbiór przesyłki przez kuriera" })
    .click();
  await page.getByRole("button", { name: "Odrzuć", exact: true }).click();
  await expect(page.getByLabel("Treść odpowiedzi")).toContainText(
    "Nie wyrażam zgody",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sprawdź swój draft" }),
  ).toBeVisible();
});

test("settings status is visible without secrets", async ({ page }) => {
  await page.goto("/settings");
  await expect(
    page.getByRole("button", { name: "Połącz konto Gmail" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Włącz na tym urządzeniu" }),
  ).toBeDisabled();
  await expect(page.getByRole("button", { name: "Zapisz podpis" })).toBeVisible();
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
