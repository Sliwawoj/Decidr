import { request } from "./api";

async function pushRegistration() {
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
  await navigator.serviceWorker.register("/sw.js");
  return navigator.serviceWorker.ready;
}

export async function isPushSubscribed() {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window))
      return false;
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) return false;
    return Boolean(await registration.pushManager.getSubscription());
  } catch {
    return false;
  }
}

export async function subscribeToPush(publicKey: string) {
  const registration = await pushRegistration();
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw new Error(
      "Powiadomienia nie zostały włączone. Nadal możesz korzystać z kolejki.",
    );
  const decoded = atob(publicKey.replace(/-/g, "+").replace(/_/g, "/"));
  const applicationServerKey = new Uint8Array(
    [...decoded].map((char) => char.charCodeAt(0)),
  );
  // Drop a previous subscription if VAPID keys changed (common after fixing .env).
  const existing = await registration.pushManager.getSubscription();
  if (existing) await existing.unsubscribe();
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey,
  });
  await request("/push/subscriptions", "POST", subscription.toJSON());
}

export async function unsubscribeFromPush() {
  const registration = await pushRegistration();
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  await request(
    "/push/subscriptions?endpoint=" + encodeURIComponent(subscription.endpoint),
    "DELETE",
  );
  await subscription.unsubscribe();
}
