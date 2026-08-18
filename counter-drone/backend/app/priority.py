"""
Confidence calibration and operator priority.

Two related jobs:

  calibrate_confidence()  the model says 94%. Should you believe it yet?
  score_priority()        of nine tracks on screen, which one first?

Both return their working, not just a number — same contract as the evidence
feature, because a score an operator can't interrogate is a score they will
eventually learn to ignore.

Scope note: "priority" here means *attention* — the order in which a human
should look at what the sensor is reporting. It ranks nothing beyond that.
"""

from collections import deque

# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------
PRIOR = 1.0 / 3.0          # three classes, so an uninformed guess is 1/3
MATURE_AT_REPORTS = 12     # reports before a track's history is fully trusted
STABILITY_WINDOW = 8       # how many past verdicts count toward steadiness


def calibrate_confidence(
    raw: float,
    label: str,
    n_reports: int,
    recent_labels: deque | list,
) -> tuple[float, list[dict]]:
    """
    Shrink a raw model probability toward the uninformed prior when the
    evidence behind it is thin.

        calibrated = PRIOR + (raw - PRIOR) * maturity * stability

    A forest asked about a four-report track will still answer 0.95, because
    nothing in `predict_proba` knows how little it was given. Two things
    genuinely should temper that:

      maturity   how many reports the window contains
      stability  whether the verdict has been holding steady or flip-flopping

    Both are 0-1 multipliers, so a young or unstable track collapses toward
    33% — an honest "I don't know yet" — while a mature steady one is left
    essentially untouched.
    """
    if label == "unknown" or n_reports <= 0:
        return 0.0, []

    maturity = min(1.0, n_reports / MATURE_AT_REPORTS)

    window = list(recent_labels)[-STABILITY_WINDOW:]
    stability = (
        sum(1 for past in window if past == label) / len(window) if window else 0.5
    )

    calibrated = PRIOR + (raw - PRIOR) * maturity * stability

    basis = [
        {
            "name": "Model probability",
            "value": round(raw, 3),
            "note": f"what the classifier reported for {label}",
        },
        {
            "name": "Track maturity",
            "value": round(maturity, 2),
            "note": f"{n_reports} of {MATURE_AT_REPORTS} reports needed for full weight",
        },
        {
            "name": "Verdict stability",
            "value": round(stability, 2),
            "note": f"{sum(1 for p in window if p == label)} of last {len(window)} agreed",
        },
    ]
    return max(0.0, min(1.0, calibrated)), basis


# --------------------------------------------------------------------------
# Priority
# --------------------------------------------------------------------------
LEVELS = [
    (75, "urgent"),
    (50, "elevated"),
    (25, "watch"),
    (0, "routine"),
]

# Each factor's maximum points. They sum to 100.
WEIGHTS = {
    "identity": 40,
    "proximity": 25,
    "closing": 20,
    "time_to_ring": 10,
    "persistence": 5,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def closing_rate(samples: list[dict], window: int = 5) -> float:
    """Metres per second of approach, averaged over recent reports."""
    recent = samples[-(window + 1) :]
    if len(recent) < 2:
        return 0.0

    total = 0.0
    seconds = 0.0
    for i in range(1, len(recent)):
        elapsed = (recent[i]["timestamp"] - recent[i - 1]["timestamp"]).total_seconds()
        if elapsed <= 0:
            continue
        total += recent[i - 1]["distance_m"] - recent[i]["distance_m"]
        seconds += elapsed

    return total / seconds if seconds > 0 else 0.0


def score_priority(
    label: str,
    calibrated_confidence: float,
    distance_m: float,
    n_reports: int,
    approach_mps: float,
    alert_radius_m: float,
    detection_range_m: float,
) -> tuple[int, str, list[dict]]:
    """
    Rank how much operator attention this track deserves, 0-100.

    Returns (score, level, factors). Every factor carries the points it
    contributed and a sentence explaining them, so a surprising score can
    always be traced to the measurement that caused it.
    """
    factors: list[dict] = []

    # 1 ── Identity. A confident drone dominates; anything else barely scores.
    if label == "drone":
        identity = calibrated_confidence
        identity_note = f"classified drone at {calibrated_confidence:.0%} calibrated confidence"
    elif label == "unknown":
        identity = 0.25
        identity_note = "not yet classified — unknowns get a small standing weight"
    else:
        identity = 0.05
        identity_note = f"classified {label}, which is not the thing being watched for"
    factors.append(
        {"name": "Identity", "points": round(WEIGHTS["identity"] * identity, 1),
         "max": WEIGHTS["identity"], "note": identity_note}
    )

    # 2 ── Proximity. Full marks inside the ring, tapering to zero at the edge.
    if distance_m <= alert_radius_m:
        proximity = 1.0
        proximity_note = f"inside the {alert_radius_m:.0f} m ring at {distance_m:.0f} m"
    else:
        outer = max(1.0, detection_range_m - alert_radius_m)
        proximity = _clamp(1.0 - (distance_m - alert_radius_m) / outer)
        proximity_note = f"{distance_m:.0f} m out, ring at {alert_radius_m:.0f} m"
    factors.append(
        {"name": "Proximity", "points": round(WEIGHTS["proximity"] * proximity, 1),
         "max": WEIGHTS["proximity"], "note": proximity_note}
    )

    # 3 ── Closing. Only inbound movement counts; departing scores nothing.
    closing = _clamp(approach_mps / 15.0)
    closing_note = (
        f"closing at {approach_mps:.1f} m/s"
        if approach_mps > 0.5
        else f"not closing ({approach_mps:+.1f} m/s)"
    )
    factors.append(
        {"name": "Closing", "points": round(WEIGHTS["closing"] * closing, 1),
         "max": WEIGHTS["closing"], "note": closing_note}
    )

    # 4 ── Time to ring. Distance alone is misleading — 2 km closing fast
    #      deserves more attention than 1 km drifting sideways.
    if approach_mps > 0.5 and distance_m > alert_radius_m:
        seconds = (distance_m - alert_radius_m) / approach_mps
        urgency = _clamp(1.0 - seconds / 180.0)
        eta_note = f"about {seconds:.0f} s from the ring at current rate"
    elif distance_m <= alert_radius_m:
        urgency = 1.0
        eta_note = "already inside the ring"
    else:
        urgency = 0.0
        eta_note = "not on course to reach the ring"
    factors.append(
        {"name": "Time to ring", "points": round(WEIGHTS["time_to_ring"] * urgency, 1),
         "max": WEIGHTS["time_to_ring"], "note": eta_note}
    )

    # 5 ── Persistence. A track seen once could be noise.
    persistence = _clamp(n_reports / 20.0)
    factors.append(
        {"name": "Persistence", "points": round(WEIGHTS["persistence"] * persistence, 1),
         "max": WEIGHTS["persistence"], "note": f"held for {n_reports} reports"}
    )

    score = int(round(sum(f["points"] for f in factors)))
    level = next(name for threshold, name in LEVELS if score >= threshold)

    factors.sort(key=lambda f: f["points"], reverse=True)
    return score, level, factors


def summarise_priority(level: str, score: int, factors: list[dict]) -> str:
    """One line naming the two factors carrying the score."""
    top = [f["name"].lower() for f in factors[:2] if f["points"] > 0]
    if not top:
        return f"Priority {score}/100 ({level})."
    return f"Priority {score}/100 ({level}) — driven by {' and '.join(top)}."
