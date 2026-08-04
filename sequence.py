"""
Turning a track's report history into a sequence tensor.
"""

SEQ_LEN = 20  # reports per window;

SEQ_CHANNELS: list[str] = [
    "speed_mps",     # how fast
    "altitude_m",    # how high
    "turn_rate",     # signed heading change per report — the strongest signal
    "closing_rate",  # metres closer per report; positive means inbound
    "rssi_dbm",      # signal strength
]

NORM: dict[str, tuple[float, float]] = {
    #                mean   scale
    "speed_mps":    (12.0,  8.0),
    "altitude_m":   (90.0,  70.0),
    "turn_rate":    (0.0,   30.0),
    "closing_rate": (0.0,   25.0),
    "rssi_dbm":     (-75.0, 15.0),
}


def signed_turn(current: float, previous: float) -> float:
    return (current - previous + 540.0) % 360.0 - 180.0


def build_sequence(samples: list[dict]) -> list[list[float]]:
    
    if len(samples) < 2:
        return []

    window = samples[-(SEQ_LEN + 1) :]
    steps: list[list[float]] = []

    for i in range(1, len(window)):
        now, before = window[i], window[i - 1]
        raw = {
            "speed_mps": now["speed_mps"],
            "altitude_m": now["altitude_m"],
            "turn_rate": signed_turn(now["heading_deg"], before["heading_deg"]),
            "closing_rate": before["distance_m"] - now["distance_m"],
            "rssi_dbm": now["rssi_dbm"],
        }
        steps.append(
            [
                (raw[name] - NORM[name][0]) / NORM[name][1]
                for name in SEQ_CHANNELS
            ]
        )

    # Left-pad to a fixed length by repeating the oldest step we have.
    while len(steps) < SEQ_LEN:
        steps.insert(0, list(steps[0]))

    return steps[-SEQ_LEN:]
