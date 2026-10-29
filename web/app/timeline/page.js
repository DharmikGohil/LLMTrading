import Event from "@/components/Event";
import TimelineFilters from "@/components/TimelineFilters";
import { fmt, load, timeline } from "@/lib/data";

export const metadata = { title: "Timeline" };

export default function Timeline() {
  const days = timeline(load());
  return (
    <main>
      <div className="page-head">
        <span className="eyebrow">Everything, newest first</span>
        <h1>Timeline</h1>
        <p className="lede">The whole thread of the desk: every analyst call with its reasoning, every candidate the engine skipped and why, every order, and the daily reports and reviews.</p>
      </div>
      <TimelineFilters>
        {days.length ? days.map(([day, evs]) => (
          <div className="day" key={day}>
            <div className="day-label">{fmt.day(day)}</div>
            <div className="events">{evs.map((e, i) => <Event key={i} e={e} />)}</div>
          </div>
        )) : <p className="note">No activity yet.</p>}
      </TimelineFilters>
    </main>
  );
}
