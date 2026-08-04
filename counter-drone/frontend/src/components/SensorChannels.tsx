import type { ReactNode } from "react";
import type { SensorInfo, Track } from "../types";
import { BearingDial } from "./BearingDial";
import { ALERT_COLOR, CLASS_COLOR, CLASS_TEXT, compassLabel, formatBearing } from "../lib/format";

interface SensorChannelsProps {
  track: Track | null;
  sensor: SensorInfo;
}

/* ------------------------------------------------------------------ *
 * A 60x22 trace of one channel's recent history.
 *
 * Auto-scaled to the window's own min/max, so it shows *shape* rather than
 * absolute level — the number above it already gives you the level. A flat
 * line means "holding steady", which for several of these channels is the
 * whole story.
 * ------------------------------------------------------------------ */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) {
    return (
      <div className="flex h-[22px] items-center">
        <span className="readout text-[9px] text-muted/60">building history…</span>
      </div>
    );
  }

  const width = 60;
  const height = 22;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;

  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - 2 - ((value - low) / span) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastX = width;
  const lastY = height - 2 - ((values[values.length - 1] - low) / span) * (height - 4);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.25"
        strokeOpacity="0.7"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r="1.8" fill={color} />
    </svg>
  );
}

/**
 * Remove the 359 -> 1 discontinuity from a series of compass angles.
 *
 * Without this, any track crossing north draws a full-height vertical cliff in
 * its sparkline — which reads as a violent manoeuvre when nothing happened.
 * We keep adding or subtracting 360 until each step is the short way round.
 */
function unwrapAngles(values: number[]): number[] {
  if (values.length === 0) return values;
  const out = [values[0]];
  for (let i = 1; i < values.length; i += 1) {
    const step = ((values[i] - values[i - 1] + 540) % 360) - 180;
    out.push(out[i - 1] + step);
  }
  return out;
}

/** A small arrow rotated to a compass direction — for heading. */
function HeadingArrow({ deg, color }: { deg: number; color: string }) {
  return (
    <svg width={30} height={30} viewBox="0 0 30 30" aria-hidden="true" className="shrink-0">
      <circle cx="15" cy="15" r="11" fill="none" stroke="var(--color-line)" strokeWidth="1" />
      <line x1="15" y1="4" x2="15" y2="7.5" stroke="#8A97A8" strokeWidth="1" />
      <g transform={`rotate(${deg} 15 15)`}>
        <path d="M15 7 L19 21 L15 18 L11 21 Z" fill={color} />
      </g>
    </svg>
  );
}

/** Five bars, filled by how far RSSI sits between -100 and -45 dBm. */
function SignalBars({ rssi, color }: { rssi: number; color: string }) {
  const strength = Math.max(0, Math.min(1, (rssi + 100) / 55));
  const lit = Math.max(1, Math.round(strength * 5));

  return (
    <svg width={30} height={22} viewBox="0 0 30 22" aria-hidden="true" className="shrink-0">
      {[0, 1, 2, 3, 4].map((i) => (
        <rect
          key={i}
          x={i * 6}
          y={20 - (i + 1) * 3.6}
          width="4"
          height={(i + 1) * 3.6}
          rx="1"
          fill={i < lit ? color : "var(--color-line)"}
        />
      ))}
    </svg>
  );
}

/** A horizontal bar showing where a value sits in a known span. */
function Gauge({ value, min, max, color }: { value: number; min: number; max: number; color: string }) {
  const fraction = Math.max(0, Math.min(1, (value - min) / (max - min)));
  return (
    <div className="h-[6px] w-full overflow-hidden rounded-full bg-line">
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{ width: `${fraction * 100}%`, backgroundColor: color }}
      />
    </div>
  );
}

interface ChannelCardProps {
  channel: string;
  field: string;
  meaning: string;
  value: string;
  visual: ReactNode;
  note?: string;
}

function ChannelCard({ channel, field, meaning, value, visual, note }: ChannelCardProps) {
  return (
    <div className="rounded-md border border-line bg-panel px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="legend">{channel}</span>
        <code className="readout text-[10px] text-muted/70">{field}</code>
      </div>

      <p className="mt-0.5 text-[11px] leading-tight text-muted">{meaning}</p>

      <p className="readout mt-2 text-lg leading-none text-ink">{value}</p>

      <div className="mt-2 flex h-[24px] items-center gap-2">{visual}</div>

      {note && <p className="readout mt-1.5 text-[10px] text-muted/60">{note}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The panel.
 *
 * Six cards, one per raw sensor channel. Each names the channel, shows the
 * exact API field it comes from, says in one line what it means, gives the
 * live value, and draws the last 40 reports.
 *
 * It stays on screen with the definitions visible even when nothing is
 * selected, so the schema is learnable without having to click something.
 * ------------------------------------------------------------------ */
export function SensorChannels({ track, sensor }: SensorChannelsProps) {
  const colour = track
    ? track.in_alert_zone
      ? ALERT_COLOR
      : CLASS_COLOR[track.classification]
    : "#9AA9BA";

  // Both Track and TrackPoint carry these six fields, so one accessor works
  // for the history *and* for the current report appended on the end.
  type Channels = Pick<
    Track,
    "distance_m" | "bearing_deg" | "altitude_m" | "speed_mps" | "heading_deg" | "rssi_dbm"
  >;
  const series = (pick: (point: Channels) => number): number[] =>
    track ? [...track.history.map(pick), pick(track)] : [];

  const dash = "—";

  return (
    <section className="panel mt-4 p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="legend">Sensor channels</h2>
        {track ? (
          <>
            <span className="readout text-sm text-ink">{track.track_id}</span>
            <span
              className={`font-display text-[11px] font-semibold uppercase ${
                track.in_alert_zone ? "text-rose" : CLASS_TEXT[track.classification]
              }`}
              style={{ letterSpacing: "var(--tracking-label)" }}
            >
              {track.classification}
              {track.confidence > 0 && ` ${Math.round(track.confidence * 100)}%`}
            </span>
            <span className="readout text-[11px] text-muted">
              {track.detection_count} reports
            </span>
          </>
        ) : (
          <span className="text-[12px] text-muted">
            Six raw values arrive per object, per tick. Select a track to see them live.
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {/* 1 ── RANGE ------------------------------------------------- */}
        <ChannelCard
          channel="Range"
          field="distance_m"
          meaning="How far away it is, in metres."
          value={
            track
              ? track.distance_m < 1000
                ? `${Math.round(track.distance_m)} m`
                : `${(track.distance_m / 1000).toFixed(2)} km`
              : dash
          }
          visual={
            track ? (
              <div className="w-full">
                <Gauge value={sensor.range_m - track.distance_m} min={0} max={sensor.range_m} color={colour} />
              </div>
            ) : (
              <Gauge value={0} min={0} max={1} color={colour} />
            )
          }
          note={
            track
              ? `alert ring at ${Math.round(sensor.alert_radius_m)} m · coverage ${(sensor.range_m / 1000).toFixed(1)} km`
              : "bar fills as an object closes in"
          }
        />

        {/* 2 ── BEARING ----------------------------------------------- */}
        <ChannelCard
          channel="Bearing"
          field="bearing_deg"
          meaning="Which compass direction it lies in, from us."
          value={track ? `${formatBearing(track.bearing_deg)} ${track.compass}` : dash}
          visual={
            <>
              <BearingDial
                bearing={track?.bearing_deg ?? 0}
                rangeFraction={track ? track.distance_m / sensor.range_m : 0.7}
                color={colour}
              />
              <Sparkline values={unwrapAngles(series((p) => p.bearing_deg))} color={colour} />
            </>
          }
          note="where it is — not where it is going"
        />

        {/* 3 ── HEADING ----------------------------------------------- */}
        <ChannelCard
          channel="Heading"
          field="heading_deg"
          meaning="Which way it is travelling."
          value={track ? `${formatBearing(track.heading_deg)} ${compassLabel(track.heading_deg)}` : dash}
          visual={
            <>
              <HeadingArrow deg={track?.heading_deg ?? 0} color={colour} />
              <Sparkline values={unwrapAngles(series((p) => p.heading_deg))} color={colour} />
            </>
          }
          note="a flat trace means straight flight"
        />

        {/* 4 ── SPEED ------------------------------------------------- */}
        <ChannelCard
          channel="Speed"
          field="speed_mps"
          meaning="How fast it is moving over the ground."
          value={track ? `${track.speed_mps.toFixed(1)} m/s` : dash}
          visual={
            <>
              <Sparkline values={series((p) => p.speed_mps)} color={colour} />
              <div className="flex-1">
                <Gauge value={track?.speed_mps ?? 0} min={0} max={30} color={colour} />
              </div>
            </>
          }
          note={track ? `${(track.speed_mps * 3.6).toFixed(0)} km/h` : "0–30 m/s scale"}
        />

        {/* 5 ── ALTITUDE ---------------------------------------------- */}
        <ChannelCard
          channel="Altitude"
          field="altitude_m"
          meaning="How high above the ground it is."
          value={track ? `${Math.round(track.altitude_m)} m` : dash}
          visual={
            <>
              <Sparkline values={series((p) => p.altitude_m)} color={colour} />
              <div className="flex-1">
                <Gauge value={track?.altitude_m ?? 0} min={0} max={250} color={colour} />
              </div>
            </>
          }
          note={track ? `${Math.round(track.altitude_m * 3.281)} ft` : "0–250 m scale"}
        />

        {/* 6 ── RF ---------------------------------------------------- */}
        <ChannelCard
          channel="Signal"
          field="rssi_dbm"
          meaning="How loud its radio signal is. Less negative is louder."
          value={track ? `${track.rssi_dbm.toFixed(1)} dBm` : dash}
          visual={
            <>
              <SignalBars rssi={track?.rssi_dbm ?? -100} color={colour} />
              <Sparkline values={series((p) => p.rssi_dbm)} color={colour} />
            </>
          }
          note="powered drones are loud; birds are faint returns"
        />
      </div>

      {track && (
        <p className="mt-3 text-[11px] leading-relaxed text-muted/70">
          These six numbers are the entire raw report. Everything else on this screen —
          the classification, the trail, the alerts — is computed from a window of them
          over time. One report on its own cannot tell you what an object is.
        </p>
      )}
    </section>
  );
}
