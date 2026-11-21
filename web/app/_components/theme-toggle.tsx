"use client";

// Light/dark theme button and the useTheme() hook (reads <html data-theme>, persists to localStorage). No API data.
import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { THEME_STORAGE_KEY } from "../theme-config";

type Theme = "light" | "dark";
const listeners = new Set<() => void>();
const readTheme = (): Theme => document.documentElement.dataset.theme === "light" ? "light" : "dark";
const serverTheme = (): Theme => "dark";
const notify = () => listeners.forEach(listener => listener());

function applyTheme(theme: Theme, preference: "manual" | "system") {
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = preference;
  notify();
}

let stopListening: (() => void) | undefined;
function subscribeTheme(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const syncSystem = () => {
      if (document.documentElement.dataset.themePreference !== "manual") applyTheme(media.matches ? "light" : "dark", "system");
    };
    const syncStorage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      if (event.newValue === "light" || event.newValue === "dark") applyTheme(event.newValue, "manual");
      else applyTheme(media.matches ? "light" : "dark", "system");
    };
    media.addEventListener("change", syncSystem);
    window.addEventListener("storage", syncStorage);
    stopListening = () => {
      media.removeEventListener("change", syncSystem);
      window.removeEventListener("storage", syncStorage);
    };
    syncSystem();
  }
  return () => {
    listeners.delete(listener);
    if (!listeners.size) { stopListening?.(); stopListening = undefined; }
  };
}

export const useTheme = () => useSyncExternalStore(subscribeTheme, readTheme, serverTheme);

export default function ThemeToggle() {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return <button type="button" className="theme-toggle" aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`} onClick={() => {
    applyTheme(next, "manual");
    try { localStorage.setItem(THEME_STORAGE_KEY, next); } catch { /* The current tab still works when storage is unavailable. */ }
  }}>
    {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
    <span>{next === "light" ? "Light mode" : "Dark mode"}</span>
  </button>;
}
