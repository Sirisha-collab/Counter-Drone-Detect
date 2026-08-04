import math
from statistics import correlation, mean, pstdev

from ..geo import haversine_m

# Assumed path loss, in dB per decade of range.
PATH_LOSS_DB_PER_DECADE = 15.0


FEATURE_SPECS: dict[str, tuple[str, str, str, str]] = {
    # ---- Range channel ---------------------------------------------------
    "mean_range_m": (
        "range", "m",
        "Average distance over the window.",
        "Weak on its own — included as context for range-dependent features.",
    ),
    "closing_rate_mps": (
        "range", "m/s",
        "Average rate the object closes on the sensor. Positive = inbound.",
        "A purposeful contact closes steadily. Clutter hovers near zero.",
    ),
    "closing_rate_std": (
        "range", "m/s",
        "Spread of the closing rate.",
        "Steady approach versus drifting. Low for a transiting drone.",
    ),
    "min_range_m": (
        "range", "m",
        "Closest approach seen so far.",
        "Operationally the number that matters most, whatever the object is.",
    ),

    # ---- Bearing channel -------------------------------------------------
    "bearing_rate_dps": (
        "bearing", "deg/s",
        "Average absolute change in bearing per second.",
        "High bearing rate at long range implies very high true speed.",
    ),
    "cross_range_speed_mps": (
        "bearing", "m/s",
        "Tangential velocity: bearing rate in radians per second times range.",
        "Separates 'fast but flying at us' from 'fast across our front'.",
    ),
    "bearing_span_deg": (
        "bearing", "deg",
        "Total angular sweep between the extreme bearings in the window.",
        "A wide sweep at close range means an overflight, not a transit.",
    ),

    # ---- Heading channel -------------------------------------------------
    "turn_rate_dps": (
        "heading", "deg/s",
        "Average absolute heading change per second.",
        "The strongest single discriminator. Birds turn constantly, "
        "drones fly straight legs.",
    ),
    "turn_rate_std": (
        "heading", "deg/s",
        "Spread of the turn rate.",
        "Distinguishes constant wander from occasional deliberate turns.",
    ),
    "heading_reversals": (
        "heading", "count",
        "How often the turn direction flips sign in the window.",
        "Jitter has many reversals. A commanded turn has none.",
    ),
    "straightness": (
        "heading", "ratio 0-1",
        "Net displacement divided by total path length.",
        "1.0 is a perfect straight line; 0.1 is a wandering scribble. "
        "Scale-free, so it works at any speed or range.",
    ),

    # ---- Speed channel ---------------------------------------------------
    "mean_speed_mps": (
        "speed", "m/s",
        "Average ground speed.",
        "Coarse separation: clutter is slow, fixed-wing is fast.",
    ),
    "speed_std_mps": (
        "speed", "m/s",
        "Spread of speed over the window.",
        "A powered vehicle holds a commanded speed; a bird does not.",
    ),
    "speed_cv": (
        "speed", "ratio",
        "Coefficient of variation: speed spread divided by mean speed.",
        "Scale-free version of the above. A slow steady object and a fast "
        "steady object score the same, which is what you want.",
    ),
    "max_speed_mps": (
        "speed", "m/s",
        "Fastest report in the window.",
        "Catches short dashes that the mean would average away.",
    ),

    # ---- Altitude channel ------------------------------------------------
    "mean_altitude_m": (
        "altitude", "m",
        "Average height.",
        "Ground clutter clusters low; fixed-wing sits high.",
    ),
    "altitude_std_m": (
        "altitude", "m",
        "Spread of altitude.",
        "Level flight versus bobbing.",
    ),
    "climb_rate_mps": (
        "altitude", "m/s",
        "Average absolute vertical rate.",
        "Birds thermal and dive; a transiting drone holds altitude.",
    ),

    # ---- RF channel ------------------------------------------------------
    "mean_rssi_dbm": (
        "rf", "dBm",
        "Average received signal strength.",
        "A powered emitter is far louder than a passive return — but this "
        "is contaminated by range, which is what the next feature fixes.",
    ),
    "rssi_std_db": (
        "rf", "dB",
        "Spread of signal strength.",
        "A real transmitter is stable. Clutter flickers badly.",
    ),
    "rssi_corrected_dbm": (
        "rf", "dBm",
        "Signal strength with the expected path loss added back — an "
        "estimate of the emitter's power at a 1 km reference distance.",
        "This is the honest version of mean_rssi_dbm. The same drone at "
        "0.5 km and 3 km gives the same value, so the model doesn't have to "
        "waste capacity learning to undo range.",
    ),
    "rssi_corrected_std": (
        "rf", "dB",
        "Spread of the range-corrected signal.",
        "Once range is removed, what's left is genuine emitter instability.",
    ),
    "rssi_range_corr": (
        "rf", "ratio -1..1",
        "Pearson correlation between signal strength and log range.",
        "A real emitter obeys the inverse-distance law, so this sits near "
        "-1. Noise that happens to look like a track does not.",
    ),

    # ---- Track quality ---------------------------------------------------
    "n_reports": (
        "quality", "count",
        "How many detections this track has accumulated.",
        "Not about the object — about how much to trust the rest.",
    ),
    "track_duration_s": (
        "quality", "s",
        "Wall-clock age of the track.",
        "A one-second-old track's features are mostly noise.",
    ),
}

FEATURE_NAMES_ALL: list[str] = list(FEATURE_SPECS)

CHANNELS: dict[str, list[str]] = {}
for _name, (_channel, *_rest) in FEATURE_SPECS.items():
    CHANNELS.setdefault(_channel, []).append(_name)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _signed_turn(current: float, previous: float) -> float:

    return (current - previous + 540.0) % 360.0 - 180.0


def _angular_span(bearings: list[float]) -> float:

    offsets = [_signed_turn(b, bearings[0]) for b in bearings]
    return max(offsets) - min(offsets)


def _safe_std(values: list[float]) -> float:
    return pstdev(values) if len(values) > 1 else 0.0


def _seconds(a: dict, b: dict) -> float:

    return max(1e-3, (a["timestamp"] - b["timestamp"]).total_seconds())


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def extract_all(samples: list[dict]) -> dict[str, float]:

    if len(samples) < 2:
        return dict.fromkeys(FEATURE_NAMES_ALL, 0.0)

    ranges = [s["distance_m"] for s in samples]
    bearings = [s["bearing_deg"] for s in samples]
    headings = [s["heading_deg"] for s in samples]
    speeds = [s["speed_mps"] for s in samples]
    altitudes = [s["altitude_m"] for s in samples]
    rssis = [s["rssi_dbm"] for s in samples]

    # Per-step differences, each divided by its own elapsed time so an
    # irregular report interval doesn't distort the rates.
    closing, bearing_rates, turn_rates, signed_turns, climb_rates = [], [], [], [], []
    path_length = 0.0

    for i in range(1, len(samples)):
        now, before = samples[i], samples[i - 1]
        dt = _seconds(now, before)

        closing.append((before["distance_m"] - now["distance_m"]) / dt)
        bearing_rates.append(abs(_signed_turn(now["bearing_deg"], before["bearing_deg"])) / dt)

        turn = _signed_turn(now["heading_deg"], before["heading_deg"])
        signed_turns.append(turn)
        turn_rates.append(abs(turn) / dt)

        climb_rates.append(abs(now["altitude_m"] - before["altitude_m"]) / dt)
        path_length += haversine_m(before["lat"], before["lon"], now["lat"], now["lon"])

    # Straightness: how directly it got from A to B.
    net = haversine_m(samples[0]["lat"], samples[0]["lon"], samples[-1]["lat"], samples[-1]["lon"])
    straightness = net / path_length if path_length > 1e-6 else 0.0

    # Turn-direction flips — a proxy for jitter versus deliberate manoeuvre.
    reversals = sum(
        1
        for i in range(1, len(signed_turns))
        if signed_turns[i] * signed_turns[i - 1] < 0
    )

    # Range-corrected RF: add back the path loss we expect at this distance.
    corrected = [
        s["rssi_dbm"] + PATH_LOSS_DB_PER_DECADE * math.log10(max(0.05, s["distance_m"] / 1000.0))
        for s in samples
    ]

    log_ranges = [math.log10(max(0.05, r / 1000.0)) for r in ranges]
    try:
        rssi_corr = correlation(rssis, log_ranges)
    except Exception:
        # Undefined when either series is constant — e.g. a hovering object.
        rssi_corr = 0.0

    mean_speed = mean(speeds)
    mean_range = mean(ranges)
    mean_bearing_rate = mean(bearing_rates)

    return {
        # range
        "mean_range_m": mean_range,
        "closing_rate_mps": mean(closing),
        "closing_rate_std": _safe_std(closing),
        "min_range_m": min(ranges),
        # bearing
        "bearing_rate_dps": mean_bearing_rate,
        "cross_range_speed_mps": math.radians(mean_bearing_rate) * mean_range,
        "bearing_span_deg": _angular_span(bearings),
        # heading
        "turn_rate_dps": mean(turn_rates),
        "turn_rate_std": _safe_std(turn_rates),
        "heading_reversals": float(reversals),
        "straightness": straightness,
        # speed
        "mean_speed_mps": mean_speed,
        "speed_std_mps": _safe_std(speeds),
        "speed_cv": _safe_std(speeds) / mean_speed if mean_speed > 1e-6 else 0.0,
        "max_speed_mps": max(speeds),
        # altitude
        "mean_altitude_m": mean(altitudes),
        "altitude_std_m": _safe_std(altitudes),
        "climb_rate_mps": mean(climb_rates),
        # rf
        "mean_rssi_dbm": mean(rssis),
        "rssi_std_db": _safe_std(rssis),
        "rssi_corrected_dbm": mean(corrected),
        "rssi_corrected_std": _safe_std(corrected),
        "rssi_range_corr": rssi_corr,
        # quality
        "n_reports": float(len(samples)),
        "track_duration_s": _seconds(samples[-1], samples[0]),
    }


def extract_vector(samples: list[dict], names: list[str] | None = None) -> list[float]:

    values = extract_all(samples)
    return [values[name] for name in (names or FEATURE_NAMES_ALL)]
