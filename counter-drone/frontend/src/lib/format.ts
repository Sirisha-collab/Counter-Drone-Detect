import type { Classification, PriorityLevel, Severity } from "../types";

/** Under a kilometre, metres read better than a decimal. */
export function formatRange(metres: number): string {
  return metres < 1000
    ? `${Math.round(metres)} m`
    : `${(metres / 1000).toFixed(2)} km`;
}

export function formatSpeed(mps: number): string {
  return `${mps.toFixed(1)} m/s`;
}

/** Bearings are always three digits — 047°, never 47°. */
export function formatBearing(deg: number): string {
  return `${Math.round(deg).toString().padStart(3, "0")}°`;
}

const COMPASS_POINTS = [
  "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
];

/** 047 -> "NE". The backend sends this for bearing; heading needs it too. */
export function compassLabel(deg: number): string {
  const index = Math.round((((deg % 360) + 360) % 360) / 22.5) % 16;
  return COMPASS_POINTS[index];
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = s % 60;
  return h > 0
    ? `${h}h ${m.toString().padStart(2, "0")}m`
    : `${m}m ${rest.toString().padStart(2, "0")}s`;
}

export function elapsedSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 1000;
}

/**
 * One colour per class, used everywhere that class appears — map dot, list
 * row, chip. Consistency is what makes the colour readable at a glance.
 */
export const CLASS_COLOR: Record<Classification, string> = {
  drone: "#B26A00",
  bird: "#157F4E",
  clutter: "#5A6878",
  unknown: "#0A7EA4",
};

export const CLASS_TEXT: Record<Classification, string> = {
  drone: "text-amber",
  bird: "text-sage",
  clutter: "text-muted",
  unknown: "text-ice",
};

export const CLASS_BORDER: Record<Classification, string> = {
  drone: "border-amber/40",
  bird: "border-sage/40",
  clutter: "border-muted/30",
  unknown: "border-ice/40",
};

export const SEVERITY_COLOR: Record<Severity, string> = {
  info: "text-muted",
  caution: "text-amber",
  alert: "text-rose",
};

export const ALERT_COLOR = "#D01B3C";

/** Priority levels get their own ramp, separate from classification colour. */
export const PRIORITY_COLOR: Record<PriorityLevel, string> = {
  routine: "#5A6878",
  watch: "#0A7EA4",
  elevated: "#B26A00",
  urgent: "#D01B3C",
};

export const PRIORITY_TEXT: Record<PriorityLevel, string> = {
  routine: "text-muted",
  watch: "text-ice",
  elevated: "text-amber",
  urgent: "text-rose",
};
