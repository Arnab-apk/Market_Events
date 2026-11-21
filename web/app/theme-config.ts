export const THEME_STORAGE_KEY = "market-events-theme";

// Runs before paint so a saved light preference never flashes the dark palette.
export const THEME_INIT_SCRIPT = `(()=>{const root=document.documentElement;let saved=null;try{saved=localStorage.getItem("${THEME_STORAGE_KEY}")}catch{}const manual=saved==="light"||saved==="dark";root.dataset.theme=manual?saved:(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");root.dataset.themePreference=manual?"manual":"system"})()`;
