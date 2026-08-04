import type { DetectionEvent } from "../types";
import { SEVERITY_COLOR, formatClock } from "../lib/format";

interface EventLogProps {
  events: DetectionEvent[];
  onSelect: (trackId: string | null) => void;
}

const SEVERITY_MARK: Record<string, string> = {
  info: "bg-muted/50",
  caution: "bg-amber",
  alert: "bg-rose",
};

export function EventLog({ events, onSelect }: EventLogProps) {
  return (
    <section className="panel flex min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <h2 className="legend">Event log</h2>
        <span className="readout text-[11px] text-muted">newest first</span>
      </div>

      {events.length === 0 ? (
        <p className="px-3 py-8 text-center text-sm text-muted">
          Events appear here as tracks open, get classified, cross the alert ring, or drop.
        </p>
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {events.map((event, index) => (
            <li
              key={`${event.timestamp}-${event.track_id ?? "sys"}-${event.event_type}-${index}`}
              className="animate-slide-in border-b border-line/40 last:border-0"
            >
              <button
                type="button"
                disabled={!event.track_id}
                onClick={() => event.track_id && onSelect(event.track_id)}
                className="flex w-full items-start gap-2.5 px-3 py-2 text-left transition-colors enabled:hover:bg-raised/60 disabled:cursor-default"
              >
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                    SEVERITY_MARK[event.severity] ?? "bg-muted/50"
                  }`}
                />
                <span className="readout shrink-0 pt-px text-[11px] text-muted/70">
                  {formatClock(event.timestamp)}
                </span>
                <span className={`text-[12px] leading-snug ${SEVERITY_COLOR[event.severity]}`}>
                  {event.message}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
