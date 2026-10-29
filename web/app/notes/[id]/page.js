import { marked } from "marked";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fmt, load } from "@/lib/data";

export function generateStaticParams() {
  return load().docs.map((d) => ({ id: d.id }));
}

export async function generateMetadata({ params }) {
  const { id } = await params;
  const d = load().docs.find((x) => x.id === id);
  return { title: d ? `${d.market} ${d.kind} ${d.date}` : "Note" };
}

export default async function Note({ params }) {
  const { id } = await params;
  const doc = load().docs.find((x) => x.id === id);
  if (!doc) notFound();
  // content comes from this repository (analyst reports and reviews); raw HTML in it is escaped
  const renderer = new marked.Renderer();
  renderer.html = ({ text }) => text.replace(/</g, "&lt;");
  const html = marked.parse(doc.body, { renderer, gfm: true });
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">{doc.market} · {doc.kind === "report" ? `analyst report, data to ${fmt.day(doc.date)}` : doc.kind === "review" ? `daily review, ${fmt.day(doc.date)}` : "change log"}</span>
        <Link className="note" href="/journal">← Journal</Link>
      </div>
      <article className="card prose" dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}
