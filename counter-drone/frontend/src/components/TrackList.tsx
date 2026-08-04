import type { SensorInfo, Track } from "../types";
import { BearingDial } from "./BearingDial";
import {
  ALERT_COLOR,
  CLASS_COLOR,
  CLASS_TEXT,
  formatBearing,
  formatRange,
  formatSpeed,
} from "../lib/format";

interface TrackListProps {
  tracks: Track[];
  sensor: SensorInfo;
  selectedId: string | null;
  onSelect: (trackId: string | null) => void;
}

export function TrackList({ tracks, sensor, selectedId, onSelect }: TrackListProps) {
  return (
    <section className="panel flex min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <h2 className="legend">Active tracks</h2>
        <span className="readout text-[11px] text-muted">
          {tracks.length} held · nearest first
        </span>
      </div>

      {tracks.length === 0 ? (
        <p className="px-3 py-8 text-center text-sm text-muted">
          Nothing in coverage. New contacts appear as the simulator generates them.
        </p>
      ) : (
        <ul className="min-h-0 flex-1 divide-y divide-line/60 overflow-y-auto">
          {tracks.map((track) => {
            const selected = track.track_id === selectedId;
            const colour = track.in_alert_zone ? ALERT_COLOR : CLASS_COLOR[track.classification];

            return (
              <li key={track.track_id}>
                <button
                  type="button"
                  onClick={() => onSelect(selected ? null : track.track_id)}
                  aria-pressed={selected}
                  className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                    selected ? "bg-raised" : "hover:bg-raised/60"
                  }`}
                >
                  <BearingDial
                    bearing={track.bearing_deg}
                    rangeFraction={track.distance_m / sensor.range_m}
                    color={colour}
                  />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="readout text-sm font-medium text-ink">
                        {track.track_id}
                      </span>
                      <span
                        className={`font-display text-[10px] font-semibold uppercase tracking-label ${
                          track.in_alert_zone ? "text-rose" : CLASS_TEXT[track.classification]
                        }`}
                      >
                        {track.classification}
                        {track.confidence > 0 && ` ${Math.round(track.confidence * 100)}%`}
                      </span>
                      {track.in_alert_zone && (
                        <span className="rounded border border-rose/40 bg-rose/10 px-1.5 py-px font-display text-[9px] font-semibold uppercase tracking-label text-rose">
                          In ring
                        </span>
                      )}
                    </div>

                    <div className="readout mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted">
                      <span className="text-ink/80">{formatRange(track.distance_m)}</span>
                      <span>
                        {formatBearing(track.bearing_deg)} {track.compass}
                      </span>
                      <span>hdg {formatBearing(track.heading_deg)}</span>
                      <span>{formatSpeed(track.speed_mps)}</span>
                      <span>{Math.round(track.altitude_m)} m alt</span>
                      <span>{track.rssi_dbm.toFixed(1)} dBm</span>
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
