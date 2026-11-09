import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { MarketPill, ThemeToggle, TickerGo } from "@/components/HeadTools";
import { LiveProvider } from "@/components/Live";
import Nav, { SubNav, TabBar } from "@/components/Nav";
import { liveKeys, load, symbols } from "@/lib/data";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata = {
  title: { default: "LLMTrading", template: "%s · LLMTrading" },
  description: "Paper trading desks run by Claude: India and US stocks, Nifty options and crypto. A rules-based strategy, an LLM that can only make it safer, and a control account to measure whether it helps.",
};

export const viewport = { themeColor: "#0a0b0d" };

// set the theme before first paint (dark unless the visitor chose light)
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }) {
  const data = load();
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <LiveProvider keys={liveKeys(data)}>
          <header className="head">
            <div className="head-row">
              <Link href="/" className="brand" aria-label="LLMTrading, home">
                <span className="brand-box" aria-hidden="true">L</span>
                <span>LLMTrading</span>
              </Link>
              <Nav />
              <div className="head-tools">
                <MarketPill />
                <TickerGo symbols={symbols(data).map((s) => s.symbol)} />
                <ThemeToggle />
              </div>
            </div>
            <SubNav />
          </header>
          <div className="shell">
            {children}
            <footer className="foot">
              <span>Paper money only · not investment advice · every decision is logged</span>
              <a href="https://github.com/DharmikGohil/LLMTrading">Source on GitHub</a>
            </footer>
          </div>
          <TabBar />
        </LiveProvider>
      </body>
    </html>
  );
}
