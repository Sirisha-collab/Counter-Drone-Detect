
export type Classification = "drone" | "bird" | "clutter" | "unknown";
export type Severity = "info" | "caution" | "alert";

/** One past report — every sensor channel, so each can be sparklined. */
export interface TrackPoint {
  lat: number;
  lon: number;
  timestamp: string;

  distance_m: number;
  bearing_deg: number;
  altitude_m: number;
  speed_mps: number;
  heading_deg: number;
  rssi_dbm: number;
}

/** One reason behind a classification, with the number it rests on. */
export interface EvidenceItem {
  feature: string;
  label: string;
  value: number;
  display_value: string;
  contribution: number;
  direction: "supports" | "opposes";
  statement: string;
}

export interface Track {
  track_id: string;
  status: string;
  classification: Classification;
  confidence: number;

  lat: number;
  lon: number;
  distance_m: number;
  bearing_deg: number;
  compass: string;
  altitude_m: number;
  speed_mps: number;
  heading_deg: number;
  rssi_dbm: number;

  first_seen: string;
  last_seen: string;
  detection_count: number;
  closest_approach_m: number;
  in_alert_zone: boolean;

  evidence: EvidenceItem[];
  evidence_summary: string;

  history: TrackPoint[];
}

export interface DetectionEvent {
  id?: number | null;
  timestamp: string;
  track_id: string | null;
  event_type: string;
  severity: Severity;
  message: string;
}

export interface Stats {
  total_detections: number;
  active_tracks: number;
  drone_tracks: number;
  alerts_active: number;
  tracks_opened: number;
  tracks_lost: number;
  uptime_seconds: number;
}

export interface SensorInfo {
  name: string;
  lat: number;
  lon: number;
  range_m: number;
  alert_radius_m: number;
  tick_seconds: number;
}

export interface LiveFrame {
  type: "frame" | "snapshot";
  timestamp: string;
  sensor: SensorInfo;
  stats: Stats;
  tracks: Track[];
  events: DetectionEvent[];
  model_ready: boolean;
}

export type ConnectionState = "connecting" | "live" | "offline";
