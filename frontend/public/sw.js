self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
// Deliberately no fetch cache: email bodies and drafts must never be cached offline.
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    /* use a generic notification */
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Decidr", {
      body: data.body || "Nowa sprawa czeka w kolejce.",
      icon: "/favicon.svg",
      tag: "decidr-new-decision",
      data: {
        url:
          typeof data.url === "string" &&
          /^\/decisions\/[a-zA-Z0-9-]+$/.test(data.url)
            ? data.url
            : "/",
      },
    }),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin)
    .href;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(async (windows) => {
        const existing = windows.find(
          (client) => new URL(client.url).origin === self.location.origin,
        );
        if (existing) {
          await existing.navigate(url);
          return existing.focus();
        }
        return self.clients.openWindow(url);
      }),
  );
});
