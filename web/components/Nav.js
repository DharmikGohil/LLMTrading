"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "Overview"],
  ["/timeline", "Timeline"],
  ["/desk/us", "US desk"],
  ["/desk/india", "India desk"],
  ["/calls", "Analyst calls"],
  ["/journal", "Journal"],
  ["/research", "Research"],
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="Sections">
      {LINKS.map(([href, label]) => (
        <Link key={href} href={href} aria-current={(href === "/" ? path === "/" : path.startsWith(href)) ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
