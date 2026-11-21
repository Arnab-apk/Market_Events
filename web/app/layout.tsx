import type { Metadata } from "next";
import "./globals.css";
import "./fintech-theme.css";
import "./hero.css";
import "./premium-overview.css";
import "./premium-theme.css";
import "./crypto-system.css";
import "./color-modes.css";
import "./presentation.css";
import { THEME_INIT_SCRIPT } from "./theme-config";

export const metadata: Metadata = {
  title: "Market Events · Research workspace",
  description: "Auditable event research, historical charts and strategy experiments for Indian markets.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head><body>{children}</body></html>;
}
