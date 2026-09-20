import type { AppStatus, Decision } from "@/types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 65000);
  try {
    const response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-Decidr-Client": "web" },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok)
      throw new ApiError(
        typeof data.detail === "string"
          ? data.detail
          : "Nieprawidłowe dane. Sprawdź formularz i spróbuj ponownie.",
        response.status,
      );
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error(
      "Nie udało się połączyć z serwerem. Odśwież widok, aby sprawdzić wynik ostatniej operacji.",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}
export const api = {
  status: () => request<AppStatus>("/status"),
  list: () => request<Decision[]>("/decisions"),
  detail: (id: string) => request<Decision>("/decisions/" + id),
  choose: (d: Decision, choice: "approve" | "reject") =>
    request<Decision>("/decisions/" + d.id + "/choice", "POST", {
      choice,
      version: d.version,
    }),
  edit: (d: Decision, draft: string) =>
    request<Decision>("/decisions/" + d.id + "/draft", "PATCH", {
      draft,
      version: d.version,
    }),
  send: (d: Decision) =>
    request<Decision>("/decisions/" + d.id + "/send", "POST", {
      confirmed: true,
      version: d.version,
    }),
  sync: () => request<{ imported: number }>("/gmail/sync", "POST"),
  login: (password: string) => request("/session", "POST", { password }),
  oauth: () => request<{ url: string }>("/oauth/gmail/start", "POST"),
};
