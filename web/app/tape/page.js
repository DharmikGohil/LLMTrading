import Filters from "@/components/Filters";
import Log from "@/components/Log";
import { Panel } from "@/components/ui";
import { load, timeline } from "@/lib/data";

export const metadata = { title: "Activity" };

export default function Tape() {
  return (
    <main>
      <div className="page-head">
        <div>
          <span className="label">The whole thread, newest first</span>
          <h1>Activity</h1>
          <p className="sub">Every analyst call with its reasoning, every candidate the engine did not buy and why, every order, and the daily reports and reviews.</p>
        </div>
      </div>
      <Filters countLabel="events" search="Filter by stock or text" groups={[
        { name: "market", label: "Desk", options: [["", "Both desks"], ["US", "US"], ["India", "India"]] },
        { name: "kind", label: "Type", options: [["", "All"], ["call", "Calls"], ["veto", "LLM vetoes"], ["skip", "Not bought"], ["order", "Orders"], ["report", "Reports"], ["review", "Reviews"]] },
      ]}>
        <Panel title="Activity log" meta="exchange-local times" flush>
          <Log days={timeline(load())} />
        </Panel>
      </Filters>
    </main>
  );
}
