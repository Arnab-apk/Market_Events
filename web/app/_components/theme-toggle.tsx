"use client";

// Appearance: the Light / Dark / System picker (Settings › Appearance) and the useTheme() hook used by
// charts. Reads <html data-theme>, persists the choice to localStorage. Light is the default. No API data.
import { useSyncExternalStore } from "react";
import { THEME_STORAGE_KEY } from "../theme-config";

export type Theme = "light" | "dark";
export type ThemeChoice = Theme | "system";
const CHOICES: { value: ThemeChoice; label: string; hint: string }[] = [
  { value: "light", label: "Light", hint: "White background (default)" },
  { value: "dark", label: "Dark", hint: "Dark background" },
  { value: "system", label: "System", hint: "Follow your device setting" },
];

const listeners = new Set<() => void>();
const root = () => document.documentElement;
const readTheme = (): Theme => root().dataset.theme === "dark" ? "dark" : "light";
const readChoice = (): ThemeChoice => {
  const preference = root().dataset.themePreference;
  return preference === "dark" || preference === "system" ? preference : "light";
};
const serverTheme = (): Theme => "light";
const serverChoice = (): ThemeChoice => "light";
const notify = () => listeners.forEach(listener => listener());
const systemDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const isChoice = (value: unknown): value is ThemeChoice => value === "light" || value === "dark" || value === "system";

function apply(choice: ThemeChoice | "default") {
  root().dataset.theme = choice === "dark" || (choice === "system" && systemDark()) ? "dark" : "light";
  root().dataset.themePreference = choice;
  notify();
}

/** Save and apply a choice. The current tab still switches when storage is blocked. */
export function setThemeChoice(choice: ThemeChoice) {
  apply(choice);
  try { localStorage.setItem(THEME_STORAGE_KEY, choice); } catch { /* storage blocked */ }
}

let stopListening: (() => void) | undefined;
function subscribeTheme(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const syncSystem = () => { if (root().dataset.themePreference === "system") apply("system"); };
    const syncStorage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      apply(isChoice(event.newValue) ? event.newValue : "default");
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

/** The theme on screen now ("light" | "dark"). */
export const useTheme = () => useSyncExternalStore(subscribeTheme, readTheme, serverTheme);
/** The saved choice ("light" | "dark" | "system"). */
export const useThemeChoice = () => useSyncExternalStore(subscribeTheme, readChoice, serverChoice);

export default function AppearancePicker() {
  const choice = useThemeChoice();
  return <fieldset className="choice-group">
    <legend>Theme</legend>
    {CHOICES.map(option => <label key={option.value} className="choice">
      <input type="radio" name="theme" value={option.value} checked={choice === option.value} onChange={() => setThemeChoice(option.value)} />
      <span><strong>{option.label}</strong><small>{option.hint}</small></span>
    </label>)}
  </fieldset>;
}
