"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

// Five sections; each may have sub-pages shown as tabs under the header.
export const SECTIONS = [
  { href: "/", label: "Home", match: (p) => p === "/", icon: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" },
  { href: "/portfolio", label: "Portfolio", match: (p) => p.startsWith("/portfolio"), icon: "M3 7h18v13H3zM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" },
  {
    href: "/desk/india", label: "Desks", match: (p) => /^\/(desk|options|crypto|symbol)/.test(p), icon: "M4 19V9M10 19V5M16 19v-7M22 19H2",
    sub: [["/desk/india", "India stocks"], ["/desk/us", "US stocks"], ["/options", "Nifty options"], ["/crypto", "Crypto"]],
  },
  {
    href: "/tape", label: "Activity", match: (p) => /^\/(tape|history|calls)/.test(p), icon: "M3 12h4l3-8 4 16 3-8h4",
    sub: [["/tape", "Latest"], ["/history", "Daily history"], ["/calls", "Analyst calls"]],
  },
  {
    href: "/journal", label: "Journal", match: (p) => /^\/(journal|research|notes)/.test(p), icon: "M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM9 9h6M9 13h6",
    sub: [["/journal", "Reviews and lessons"], ["/research", "Research"]],
  },
];

const current = (path) => SECTIONS.find((s) => s.match(path)) || SECTIONS[0];

/** Top navigation; keys 1-5 jump between sections, "/" focuses the ticker box. */
export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  useEffect(() => {
    const on = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      if (e.key === "/") {
        document.getElementById("go-input")?.focus();
        e.preventDefault();
        return;
      }
      const n = Number(e.key);
      if (n >= 1 && n <= SECTIONS.length) router.push(SECTIONS[n - 1].href);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [router]);
  const sec = current(path);
  return (
    <nav className="nav" aria-label="Sections">
      {SECTIONS.map((s) => (
        <Link key={s.href} href={s.href} aria-current={s === sec ? "page" : undefined}>{s.label}</Link>
      ))}
    </nav>
  );
}

/** Sub-pages of the current section, as tabs under the header. */
export function SubNav() {
  const path = usePathname();
  const sec = current(path);
  if (!sec.sub) return null;
  const active = sec.sub.find(([h]) => path === h || path.startsWith(`${h}/`))?.[0];
  return (
    <nav className="subnav" aria-label={`${sec.label} pages`}>
      {sec.sub.map(([href, label]) => (
        <Link key={href} href={href} aria-current={href === active ? "page" : undefined}>{label}</Link>
      ))}
    </nav>
  );
}

/** Phone: a bottom tab bar, like a broker app. */
export function TabBar() {
  const path = usePathname();
  const sec = current(path);
  return (
    <nav className="tabbar" aria-label="Sections">
      {SECTIONS.map((s) => (
        <Link key={s.href} href={s.href} aria-current={s === sec ? "page" : undefined}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={s.icon} /></svg>
          {s.label}
        </Link>
      ))}
    </nav>
  );
}
