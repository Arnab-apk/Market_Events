// Theme constants: the localStorage key and the inline script that sets <html data-theme> before paint.
// Stored choice: "light" | "dark" | "system". Nothing saved (or an unknown value) means light.
export const THEME_STORAGE_KEY = "market-events-theme";

// Runs before paint so a saved dark choice never flashes the light palette.
// data-theme-preference records the choice ("light" | "dark" | "system"); "default" when nothing is saved.
export const THEME_INIT_SCRIPT = `(()=>{const root=document.documentElement;let saved=null;try{saved=localStorage.getItem("${THEME_STORAGE_KEY}")}catch{}const known=saved==="light"||saved==="dark"||saved==="system";root.dataset.theme=saved==="dark"||(saved==="system"&&matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light";root.dataset.themePreference=known?saved:"default"})()`;
