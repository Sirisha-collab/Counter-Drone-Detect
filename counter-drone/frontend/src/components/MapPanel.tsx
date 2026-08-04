import { Fragment, useEffect, useMemo } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { SensorInfo, Track } from "../types";
import { destinationPoint } from "../lib/geo";
import { ALERT_COLOR, CLASS_COLOR, formatBearing, formatRange } from "../lib/format";

interface MapPanelProps {
  sensor: SensorInfo;
  tracks: Track[];
  selectedId: string | null;
  onSelect: (trackId: string | null) => void;
}

/** Frames the map on the outer coverage ring, once, when the site is known. */
function FitToCoverage({ sensor }: { sensor: SensorInfo }) {
  const map = useMap();
  useEffect(() => {
    const [north] = destinationPoint(sensor.lat, sensor.lon, 0, sensor.range_m);
    const [south] = destinationPoint(sensor.lat, sensor.lon, 180, sensor.range_m);
    const [, east] = destinationPoint(sensor.lat, sensor.lon, 90, sensor.range_m);
    const [, west] = destinationPoint(sensor.lat, sensor.lon, 270, sensor.range_m);
    map.fitBounds(
      [
        [south, west],
        [north, east],
      ],
      { padding: [24, 24] },
    );
  }, [map, sensor.lat, sensor.lon, sensor.range_m]);
  return null;
}

const CARDINALS: [string, number][] = [
  ["N", 0],
  ["E", 90],
  ["S", 180],
  ["W", 270],
];

export function MapPanel({ sensor, tracks, selectedId, onSelect }: MapPanelProps) {
  const centre: [number, number] = [sensor.lat, sensor.lon];

  // Three range rings plus the alert ring. Each is labelled with its real
  // distance, so the map reads as an instrument rather than a decorated map.
  const rings = useMemo(
    () => [sensor.range_m / 3, (sensor.range_m * 2) / 3, sensor.range_m],
    [sensor.range_m],
  );

  const cardinalMarkers = useMemo(
    () =>
      CARDINALS.map(([letter, bearing]) => ({
        letter,
        position: destinationPoint(sensor.lat, sensor.lon, bearing, sensor.range_m * 0.99),
        icon: L.divIcon({
          className: "compass-tick",
          html: letter,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
      })),
    [sensor.lat, sensor.lon, sensor.range_m],
  );

  const ringLabels = useMemo(
    () =>
      rings.map((radius) => ({
        radius,
        position: destinationPoint(sensor.lat, sensor.lon, 45, radius),
        icon: L.divIcon({
          className: "range-label",
          html: `${(radius / 1000).toFixed(1)} km`,
          iconSize: [40, 12],
          iconAnchor: [-4, 6],
        }),
      })),
    [rings, sensor.lat, sensor.lon],
  );

  return (
    <MapContainer
      center={centre}
      zoom={14}
      className="h-full w-full"
      scrollWheelZoom
      zoomControl
      attributionControl
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        subdomains="abcd"
        maxZoom={19}
      />

      <FitToCoverage sensor={sensor} />

      {/* Coverage rings */}
      {rings.map((radius) => (
        <Circle
          key={`ring-${radius}`}
          center={centre}
          radius={radius}
          pathOptions={{
            color: "#9AA9BA",
            weight: 1,
            fill: false,
            dashArray: radius === sensor.range_m ? undefined : "3 6",
          }}
          interactive={false}
        />
      ))}

      {/* Alert ring — the one boundary that changes behaviour */}
      <Circle
        center={centre}
        radius={sensor.alert_radius_m}
        pathOptions={{
          color: ALERT_COLOR,
          weight: 1,
          opacity: 0.55,
          fillColor: ALERT_COLOR,
          fillOpacity: 0.07,
          dashArray: "2 5",
        }}
        interactive={false}
      />

      {ringLabels.map((label) => (
        <Marker
          key={`label-${label.radius}`}
          position={label.position}
          icon={label.icon}
          interactive={false}
        />
      ))}

      {cardinalMarkers.map((cardinal) => (
        <Marker
          key={cardinal.letter}
          position={cardinal.position}
          icon={cardinal.icon}
          interactive={false}
        />
      ))}

      {/* Sensor site */}
      <CircleMarker
        center={centre}
        radius={5}
        pathOptions={{ color: "#0A7EA4", weight: 2, fillColor: "#0A7EA4", fillOpacity: 0.9 }}
      >
        <Tooltip direction="top" offset={[0, -8]}>
          <span className="font-mono text-[11px]">{sensor.name} · sensor site</span>
        </Tooltip>
      </CircleMarker>

      {/* Tracks */}
      {tracks.map((track) => {
        const colour = track.in_alert_zone ? ALERT_COLOR : CLASS_COLOR[track.classification];
        const selected = track.track_id === selectedId;
        const trail: [number, number][] = [
          ...track.history.map((point) => [point.lat, point.lon] as [number, number]),
          [track.lat, track.lon],
        ];
        const headingStub = destinationPoint(
          track.lat,
          track.lon,
          track.heading_deg,
          Math.max(90, track.speed_mps * 12),
        );

        return (
          <Fragment key={track.track_id}>
            {trail.length > 1 && (
              <Polyline
                positions={trail}
                pathOptions={{
                  color: colour,
                  weight: selected ? 2 : 1.25,
                  opacity: selected ? 0.75 : 0.4,
                }}
                interactive={false}
              />
            )}

            <Polyline
              positions={[[track.lat, track.lon], headingStub]}
              pathOptions={{ color: colour, weight: 1, opacity: 0.7 }}
              interactive={false}
            />

            {track.in_alert_zone && (
              <CircleMarker
                center={[track.lat, track.lon]}
                radius={13}
                pathOptions={{
                  color: ALERT_COLOR,
                  weight: 1,
                  opacity: 0.5,
                  fillColor: ALERT_COLOR,
                  fillOpacity: 0.14,
                }}
                interactive={false}
              />
            )}

            <CircleMarker
              center={[track.lat, track.lon]}
              radius={selected ? 8 : 5.5}
              pathOptions={{
                color: colour,
                weight: selected ? 3 : 1.5,
                fillColor: colour,
                fillOpacity: 0.85,
              }}
              eventHandlers={{
                click: () => onSelect(selected ? null : track.track_id),
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <span className="font-mono text-[11px]">
                  {track.track_id} · {track.classification} · {formatRange(track.distance_m)} ·{" "}
                  {formatBearing(track.bearing_deg)}
                </span>
              </Tooltip>
            </CircleMarker>
          </Fragment>
        );
      })}
    </MapContainer>
  );
}
