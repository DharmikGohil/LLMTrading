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
          <h1>Activity</h1>
          <p className="sub">Every call, order, veto and review across both stock desks, newest first.</p>
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
