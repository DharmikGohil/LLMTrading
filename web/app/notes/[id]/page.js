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
  const what = doc.kind === "report" ? `Analyst report · data to ${fmt.day(doc.date)}` : doc.kind === "review" ? `Close review · ${fmt.day(doc.date)}` : "Strategy change log";
  return (
    <main>
      <div className="page-head">
        <div>
          <div className="crumbs"><Link className="label" href="/journal">← Journal</Link></div>
          <h1 style={{ fontSize: 18 }}>{doc.market !== "all" ? <span className="chip ghost" style={{ marginRight: 8, verticalAlign: "middle" }}>{doc.market === "US" ? "US" : "NSE"}</span> : null}{what}</h1>
        </div>
      </div>
      <section className="panel"><div className="panel-b"><article className="prose" dangerouslySetInnerHTML={{ __html: html }} /></div></section>
    </main>
  );
}
