import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import Nav from "@/components/Nav";
import { load } from "@/lib/data";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata = {
  title: { default: "LLMTrading Desk", template: "%s · LLMTrading Desk" },
  description: "Paper trading desk run by Claude: a momentum screen picks NSE and US stocks, an LLM analyst can only veto, and a control account trades without it.",
};

export default function RootLayout({ children }) {
  const { meta } = load();
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <header className="top">
          <div className="top-inner">
            <Link href="/" className="mark"><span className="mark-dot" aria-hidden="true" />llmtrading/desk</Link>
            <Nav />
            <span className="paper" title="No real money is traded">Paper trading</span>
          </div>
        </header>
        <div className="shell">
          {children}
          <footer className="foot">
            <span>Paper money only. Not investment advice. Data synced {meta.synced_at ? new Date(meta.synced_at).toUTCString() : "—"}.</span>
            <a href="https://github.com/DharmikGohil/LLMTrading">Source</a>
          </footer>
        </div>
      </body>
    </html>
  );
}
