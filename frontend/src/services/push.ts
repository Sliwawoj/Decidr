import { request } from "./api";

export async function subscribeToPush(publicKey: string) {
  if (
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  )
    throw new Error(
      "Ta przeglądarka nie obsługuje Web Push. Kolejka działa normalnie.",
    );
  if (!window.isSecureContext)
    throw new Error("Powiadomienia wymagają HTTPS lub localhost.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw new Error(
      "Powiadomienia nie zostały włączone. Nadal możesz korzystać z kolejki.",
    );
  await navigator.serviceWorker.register("/sw.js");
  const registration = await navigator.serviceWorker.ready;
  const decoded = atob(publicKey.replace(/-/g, "+").replace(/_/g, "/"));
  const applicationServerKey = new Uint8Array(
    [...decoded].map((char) => char.charCodeAt(0)),
  );
  const subscription =
    (await registration.pushManager.getSubscription()) ||
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    }));
  await request("/push/subscriptions", "POST", subscription.toJSON());
}
