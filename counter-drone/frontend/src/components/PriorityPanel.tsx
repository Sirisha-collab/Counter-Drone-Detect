import type { Track } from "../types";
import { PRIORITY_COLOR, PRIORITY_TEXT } from "../lib/format";

interface PriorityPanelProps {
  track: Track | null;
}

const LEVEL_ORDER = ["routine", "watch", "elevated", "urgent"] as const;

/** Points earned out of points available, for one factor. */
function FactorBar({ points, max, color }: { points: number; max: number; color: string }) {
  const fraction = max > 0 ? Math.min(1, points / max) : 0;
  return (
    <div className="h-[6px] w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{ width: `${(fraction * 100).toFixed(1)}%`, backgroundColor: color }}
      />
    </div>
  );
}

export function PriorityPanel({ track }: PriorityPanelProps) {
  if (!track) {
    return (
      <section className="panel mt-4 p-3 sm:p-4">
        <h2 className="legend mb-2">Priority and confidence</h2>
        <p className="text-[12px] text-muted">
          Tracks are ranked by how much attention they warrant, not by distance alone.
          Select one to see how its score was built.
        </p>
      </section>
    );
  }

  const colour = PRIORITY_COLOR[track.priority_level];
  const raw = track.confidence;
  const calibrated = track.confidence_calibrated;
  const damped = raw - calibrated > 0.02;

  return (
    <section className="panel mt-4 p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="legend">Priority and confidence</h2>
        <span className="readout text-sm text-ink">{track.track_id}</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {/* ---- Priority score ------------------------------------------ */}
        <div>
          <div className="mb-3 flex items-baseline gap-3">
            <span className="readout text-3xl leading-none" style={{ color: colour }}>
              {track.priority_score}
            </span>
            <span className="readout text-sm text-muted">/ 100</span>
            <span
              className={`font-display text-[12px] font-semibold uppercase ${PRIORITY_TEXT[track.priority_level]}`}
              style={{ letterSpacing: "var(--tracking-label)" }}
            >
              {track.priority_level}
            </span>
          </div>

          {/* Where this score sits on the four bands */}
          <div className="mb-3 flex gap-1" aria-hidden="true">
            {LEVEL_ORDER.map((level) => (
              <div
                key={level}
                className="h-1 flex-1 rounded-full"
                style={{
                  backgroundColor:
                    LEVEL_ORDER.indexOf(level) <= LEVEL_ORDER.indexOf(track.priority_level)
                      ? colour
                      : "var(--color-line)",
                }}
              />
            ))}
          </div>

          <ul className="space-y-2.5">
            {track.priority_factors.map((factor) => (
              <li key={factor.name}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[12px] font-medium text-ink">{factor.name}</span>
                  <span className="readout text-[11px] text-muted">
                    {factor.points.toFixed(1)} / {factor.max}
                  </span>
                </div>
                <div className="mt-1">
                  <FactorBar points={factor.points} max={factor.max} color={colour} />
                </div>
                <p className="mt-1 text-[11px] leading-snug text-muted">{factor.note}</p>
              </li>
            ))}
          </ul>
        </div>

        {/* ---- Confidence calibration ---------------------------------- */}
        <div className="lg:border-l lg:border-line lg:pl-4">
          <p className="legend mb-2">Confidence</p>

          <div className="mb-1 flex items-baseline gap-2">
            <span className="readout text-2xl leading-none text-ink">
              {Math.round(calibrated * 100)}%
            </span>
            <span className="readout text-[11px] text-muted">calibrated</span>
          </div>
          <p className="readout mb-3 text-[11px] text-muted">
            model reported {Math.round(raw * 100)}%
          </p>

          <ul className="space-y-2">
            {track.confidence_basis.map((item) => (
              <li key={item.name}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] text-ink">{item.name}</span>
                  <span className="readout text-[11px] text-muted">
                    {item.value.toFixed(2)}
                  </span>
                </div>
                <p className="text-[10px] leading-snug text-muted/70">{item.note}</p>
              </li>
            ))}
          </ul>

          <p className="mt-3 text-[11px] leading-relaxed text-muted/70">
            {damped
              ? "The model is more certain than the evidence justifies. A forest asked about a four-report track still answers confidently — nothing inside it knows how little it was given. Maturity and stability temper that."
              : "Enough steady reports have accumulated that the model's own figure stands unmodified."}
          </p>
        </div>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted/70">
        Priority ranks operator attention only. Distance alone would bury a fast inbound
        contact at 2 km beneath clutter sitting at 400 m.
      </p>
    </section>
  );
}
