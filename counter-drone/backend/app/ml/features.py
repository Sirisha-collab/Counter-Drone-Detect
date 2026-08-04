from statistics import pstdev

from ..geo import angle_difference

FEATURE_NAMES: list[str] = [
    "mean_speed_mps",
    "speed_std",
    "mean_altitude_m",
    "heading_std_deg",
    "mean_rssi_dbm",
    "rssi_std",
]

CLASS_LABELS: list[str] = ["drone", "bird", "clutter"]


def extract_features(samples: list[dict]) -> list[float]:

    speeds = [s["speed_mps"] for s in samples]
    alts = [s["altitude_m"] for s in samples]
    rssis = [s["rssi_dbm"] for s in samples]
    headings = [s["heading_deg"] for s in samples]

    # Turn rate: average change in heading between consecutive reports.
    turns = [
        angle_difference(headings[i], headings[i - 1]) for i in range(1, len(headings))
    ] or [0.0]

    return [
        sum(speeds) / len(speeds),
        pstdev(speeds) if len(speeds) > 1 else 0.0,
        sum(alts) / len(alts),
        sum(turns) / len(turns),
        sum(rssis) / len(rssis),
        pstdev(rssis) if len(rssis) > 1 else 0.0,
    ]
