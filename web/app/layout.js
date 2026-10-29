import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { MarketClocks, ThemeToggle, TickerGo } from "@/components/HeadTools";
import { LiveBadge, LiveProvider } from "@/components/Live";
import Nav from "@/components/Nav";
import Tape from "@/components/Tape";
import { asOf, liveKeys, load, symbols, tape } from "@/lib/data";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata = {
  title: { default: "LLMTrading Desk", template: "%s · LLMTrading Desk" },
  description: "A paper trading desk run by Claude on NSE and US stocks: a momentum screen picks, an LLM analyst can only veto, and a control account trades without it.",
};

export const viewport = { themeColor: "#07090c" };

// set the theme before first paint (dark unless the visitor chose light)
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }) {
  const data = load();
  const updated = asOf(data);
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <LiveProvider keys={liveKeys(data)}>
        <header className="head">
          <div className="head-row">
            <Link href="/" className="brand" aria-label="LLMTrading Desk, overview">
              <span className="brand-box" aria-hidden="true">L</span>
              <span>llmtrading<b>/desk</b></span>
            </Link>
            <Nav />
            <div className="head-tools">
              <TickerGo symbols={symbols(data).map((s) => s.symbol)} />
              <ThemeToggle />
            </div>
          </div>
          <div className="status">
            <span className="paper-tag" title="No real money is traded">PAPER</span>
            <LiveBadge />
            <span className="sep" aria-hidden="true" />
            <MarketClocks asOf={updated} />
          </div>
          <Tape items={tape(data)} />
        </header>
        <div className="shell">
          {children}
          <footer className="foot">
            <span>Paper money only. Not investment advice. Run by Claude through scheduled sessions; every decision is logged.</span>
            <a href="https://github.com/DharmikGohil/LLMTrading">Source on GitHub</a>
          </footer>
        </div>
        </LiveProvider>
      </body>
    </html>
  );
}
