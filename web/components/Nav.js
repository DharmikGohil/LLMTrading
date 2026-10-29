"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

export const LINKS = [
  ["/", "Overview"],
  ["/desk/us", "US desk"],
  ["/desk/india", "India desk"],
  ["/history", "History"],
  ["/tape", "Activity"],
  ["/calls", "Analyst calls"],
  ["/journal", "Journal"],
  ["/research", "Research"],
];

/** Section tabs; keys 1-8 jump between them, "/" focuses the ticker box. */
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
      if (n >= 1 && n <= LINKS.length) router.push(LINKS[n - 1][0]);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [router]);
  return (
    <nav className="nav" aria-label="Sections">
      {LINKS.map(([href, label], i) => (
        <Link key={href} href={href} aria-current={(href === "/" ? path === "/" : path.startsWith(href)) ? "page" : undefined}>
          <kbd aria-hidden="true">{i + 1}</kbd>{label}
        </Link>
      ))}
    </nav>
  );
}
