"use client";

import { useCallback, useEffect, useState } from "react";
import type { Api } from "./types";
import { readPortfolioSnapshot } from "../_lib/portfolio";
import type { PortfolioSnapshot } from "../_lib/portfolio";

type Saved = { revision: number; snapshot: PortfolioSnapshot | null };

export function useSavedPortfolio(api: Api, storageKey: string, demo: boolean) {
  const [snapshot, setSnapshot] = useState(() => {
    try { return readPortfolioSnapshot(window.sessionStorage.getItem(storageKey)); }
    catch { return null; }
  });
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(!demo);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt(value => value + 1), []);

  function cache(next: PortfolioSnapshot | null) {
    try {
      if (next) window.sessionStorage.setItem(storageKey, JSON.stringify(next));
      else window.sessionStorage.removeItem(storageKey);
    } catch { /* The database remains authoritative when browser storage is unavailable. */ }
  }

  useEffect(() => {
    if (demo) return;
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        let saved = await api<Saved>("portfolio");
        if (!active) return;
        let legacy: PortfolioSnapshot | null = null;
        try { legacy = readPortfolioSnapshot(window.sessionStorage.getItem(storageKey)); } catch {}
        if (!saved.snapshot && saved.revision === 0 && legacy) {
          // Only previously confirmed holdings migrate; a deletion tombstone blocks resurrection.
          saved = await api<Saved>("portfolio", { revision: 0, snapshot: legacy });
        }
        if (active) {
          setSnapshot(saved.snapshot);
          setRevision(saved.revision);
          try {
            if (saved.snapshot) window.sessionStorage.setItem(storageKey, JSON.stringify(saved.snapshot));
            else window.sessionStorage.removeItem(storageKey);
          } catch {}
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Could not load the saved portfolio.");
      } finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [api, storageKey, demo, attempt]);

  async function save(next: PortfolioSnapshot | null) {
    if (loading || saving || error) throw new Error("Reload the saved portfolio before changing it.");
    setSaving(true);
    try {
      const saved = demo ? { revision, snapshot: next } : await api<Saved>("portfolio", { revision, snapshot: next });
      if (demo) {
        // Keep the offline sample isolated to this tab.
        if (next) window.sessionStorage.setItem(storageKey, JSON.stringify(next));
        else window.sessionStorage.removeItem(storageKey);
      } else cache(saved.snapshot);
      setSnapshot(saved.snapshot);
      setRevision(saved.revision);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not save the portfolio.";
      setError(message);
      throw new Error(message);
    } finally { setSaving(false); }
  }

  return { snapshot, loading, saving, error, save, reload };
}
