"use client";

// Hook: true when the operating system asks for reduced motion. Used to pause ambient effects.
import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";
const subscribe = (notify: () => void) => {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const read = () => window.matchMedia(QUERY).matches;
// Server render assumes reduced motion so effects never start before hydration.
const readOnServer = () => true;

export function useReducedMotion() {
  return useSyncExternalStore(subscribe, read, readOnServer);
}
