// Root HTML layout: loads the stylesheets in cascade order (tokens → presentation) and applies the
// saved light/dark theme before first paint. No API data.
import type { Metadata } from "next";
import "./tokens.css";
import "./base.css";
import "./layout.css";
import "./components.css";
import "./overview.css";
import "./presentation.css";
import "./research-desk.css";
import { THEME_INIT_SCRIPT } from "./theme-config";

export const metadata: Metadata = {
  title: "Market Events · Research workspace",
  description: "Auditable event research, historical charts and strategy experiments for Indian markets.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head><body>{children}</body></html>;
}
