import type { Stats } from "../types";
import { formatDuration } from "../lib/format";

interface StatStripProps {
  stats?: Stats;
}

interface Tile {
  label: string;
  value: string;
  hint: string;
  tone?: string;
}

export function StatStrip({ stats }: StatStripProps) {
  const tiles: Tile[] = [
    {
      label: "Detections",
      value: stats ? stats.total_detections.toLocaleString() : "—",
      hint: "reports received this session",
      tone: "text-ice",
    },
    {
      label: "Active tracks",
      value: stats ? String(stats.active_tracks) : "—",
      hint: "objects currently held",
    },
    {
      label: "Classed drone",
      value: stats ? String(stats.drone_tracks) : "—",
      hint: "of the active tracks",
      tone: stats && stats.drone_tracks > 0 ? "text-amber" : undefined,
    },
    {
      label: "In alert ring",
      value: stats ? String(stats.alerts_active) : "—",
      hint: "drones inside the inner ring",
      tone: stats && stats.alerts_active > 0 ? "text-rose" : undefined,
    },
    {
      label: "Opened / retired",
      value: stats ? `${stats.tracks_opened} / ${stats.tracks_lost}` : "—",
      hint: "track lifecycle totals",
    },
    {
      label: "Running",
      value: stats ? formatDuration(stats.uptime_seconds) : "—",
      hint: "since the backend started",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {tiles.map((tile) => (
        <div key={tile.label} className="panel px-3 py-2.5">
          <p className="legend">{tile.label}</p>
          <p className={`readout mt-1 text-2xl font-medium leading-none ${tile.tone ?? "text-ink"}`}>
            {tile.value}
          </p>
          <p className="mt-1.5 text-[11px] leading-tight text-muted/70">{tile.hint}</p>
        </div>
      ))}
    </div>
  );
}
