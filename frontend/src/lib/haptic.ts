/** Short tactile pulse when Vibration API is available (mostly Android). */
export function haptic(ms = 12) {
  try {
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate(ms);
    }
  } catch {
    /* ignore unsupported / blocked vibration */
  }
}
