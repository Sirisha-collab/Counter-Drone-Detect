import type { ConnectionState, SensorInfo } from "../types";

interface HeaderProps {
  sensor?: SensorInfo;
  connection: ConnectionState;
  modelReady: boolean;
}

const CONNECTION_COPY: Record<ConnectionState, { label: string; dot: string; text: string }> = {
  live: { label: "Live feed", dot: "bg-sage", text: "text-sage" },
  connecting: { label: "Connecting", dot: "bg-amber", text: "text-amber" },
  offline: { label: "Feed lost — retrying", dot: "bg-rose", text: "text-rose" },
};

export function Header({ sensor, connection, modelReady }: HeaderProps) {
  const status = CONNECTION_COPY[connection];

  return (
    <header className="border-b border-line bg-panel/80 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-xl font-semibold uppercase tracking-label text-ink">
            {sensor?.name ?? "Sensor"}
          </h1>
          <span className="legend">Counter-drone monitor</span>
        </div>

        <span className="rounded border border-ice/30 bg-ice/10 px-2 py-0.5 font-display text-[11px] font-semibold uppercase tracking-label text-ice">
          Simulated data
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-x-5 gap-y-2">
          {sensor && (
            <span className="readout hidden text-[11px] text-muted lg:inline">
              {sensor.lat.toFixed(4)}, {sensor.lon.toFixed(4)} · range{" "}
              {(sensor.range_m / 1000).toFixed(1)} km
            </span>
          )}

          <span
            className={`readout text-[11px] ${modelReady ? "text-muted" : "text-amber"}`}
            title={
              modelReady
                ? "Random forest classifier loaded"
                : "No trained model found — running the fallback rule. Train one with: python -m app.ml.train"
            }
          >
            {modelReady ? "Model: random forest" : "Model: fallback rule"}
          </span>

          <div className="flex items-center gap-2">
            <span className={`relative flex h-2 w-2 ${status.dot} rounded-full`}>
              {connection === "live" && (
                <span className="absolute inset-0 animate-pulse-ring rounded-full bg-sage" />
              )}
            </span>
            <span className={`font-display text-[11px] font-medium uppercase tracking-label ${status.text}`}>
              {status.label}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
