import type { Track } from "../types";
import { ALERT_COLOR, CLASS_COLOR, CLASS_TEXT } from "../lib/format";

interface EvidencePanelProps {
  track: Track | null;
}


function ContributionBar({ value, max, color }: { value: number; max: number; color: string }) {
  const fraction = max > 0 ? Math.min(1, Math.abs(value) / max) : 0;
  const supports = value >= 0;

  return (
    <div className="relative h-[7px] w-full" aria-hidden="true">
      <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
      <div
        className="absolute inset-y-0 rounded-sm transition-[width] duration-500"
        style={{
          width: `${(fraction * 50).toFixed(1)}%`,
          left: supports ? "50%" : undefined,
          right: supports ? undefined : "50%",
          backgroundColor: supports ? color : "var(--color-muted)",
          opacity: supports ? 0.85 : 0.5,
        }}
      />
    </div>
  );
}

export function EvidencePanel({ track }: EvidencePanelProps) {
  const colour = track
    ? track.in_alert_zone
      ? ALERT_COLOR
      : CLASS_COLOR[track.classification]
    : "#9AA9BA";

  const evidence = track?.evidence ?? [];
  const strongest = Math.max(...evidence.map((item) => Math.abs(item.contribution)), 0.0001);

  return (
    <section className="panel mt-4 p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="legend">Why this verdict</h2>
        {track && (
          <>
            <span className="readout text-sm text-ink">{track.track_id}</span>
            <span
              className={`font-display text-[11px] font-semibold uppercase ${track.in_alert_zone ? "text-rose" : CLASS_TEXT[track.classification]
                }`}
              style={{ letterSpacing: "var(--tracking-label)" }}
            >
              {track.classification}
            </span>
          </>
        )}
      </div>

      {!track ? (
        <p className="text-[12px] text-muted">
          Every classification carries its reasoning. Select a track to see which
          measurements drove it, and by how much.
        </p>
      ) : evidence.length === 0 ? (
        <p className="text-[12px] text-muted">
          Not enough reports yet — a verdict needs a few detections before there is
          anything to reason from.
        </p>
      ) : (
        <>
          <p className="mb-3 text-[13px] leading-snug text-ink/90">{track.evidence_summary}</p>

          <ul className="space-y-2.5">
            {evidence.map((item) => (
              <li
                key={item.feature}
                className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 gap-y-1 border-b border-line/50 pb-2.5 last:border-0 last:pb-0"
              >
                <div className="flex items-baseline gap-2">
                  <span className="text-[12px] font-medium text-ink">{item.label}</span>
                  <code className="readout text-[10px] text-muted/70">{item.feature}</code>
                </div>

                <span className="readout text-[12px] text-ink">{item.display_value}</span>

                <div className="col-span-2 flex items-center gap-3">
                  <div className="w-28 shrink-0 sm:w-40">
                    <ContributionBar value={item.contribution} max={strongest} color={colour} />
                  </div>
                  <span
                    className={`readout shrink-0 text-[10px] ${item.direction === "supports" ? "text-ink/70" : "text-muted"
                      }`}
                  >
                    {item.contribution >= 0 ? "+" : ""}
                    {item.contribution.toFixed(3)} {item.direction}
                  </span>
                </div>

                <p className="col-span-2 text-[11px] leading-snug text-muted">
                  {item.statement}
                </p>
              </li>
            ))}
          </ul>

          <p className="mt-3 text-[11px] leading-relaxed text-muted/70">
            Contributions come from the path this track took through every tree in the
            forest. They sum with the model's baseline to exactly the confidence shown —
            so this is what the model actually did, not a plausible-sounding story about it.
          </p>
        </>
      )}
    </section>
  );
}
