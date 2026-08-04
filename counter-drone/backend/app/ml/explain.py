from .features import FEATURE_NAMES

# Display metadata per feature: label, unit, decimal places.
FEATURE_META: dict[str, tuple[str, str, int]] = {
    "mean_speed_mps": ("Average speed", " m/s", 1),
    "speed_std": ("Speed steadiness", " m/s", 2),
    "mean_altitude_m": ("Altitude", " m", 0),
    "heading_std_deg": ("Turn per report", "°", 1),
    "mean_rssi_dbm": ("Signal strength", " dBm", 1),
    "rssi_std": ("Signal steadiness", " dB", 2),
}

# What each feature tells you, in one clause. Appended to every statement so
# the reader learns the domain reasoning, not just the number.
WHY: dict[str, str] = {
    "mean_speed_mps": "drones cruise faster than birds, clutter barely moves",
    "speed_std": "a powered vehicle holds a commanded speed",
    "mean_altitude_m": "ground clutter sits low, fixed-wing sits high",
    "heading_std_deg": "drones fly straight legs; birds turn constantly",
    "mean_rssi_dbm": "a powered transmitter is far louder than a passive return",
    "rssi_std": "a real emitter is stable; clutter flickers",
}

# Measured class averages, from `python -m app.ml.analyze_features`.
# Used only for the "closest to a typical X" phrasing — never for the
# prediction itself, which comes from the model.
TYPICAL: dict[str, dict[str, float]] = {
    "mean_speed_mps":  {"drone": 15.9, "bird": 9.3,  "clutter": 5.4},
    "speed_std":       {"drone": 1.15, "bird": 2.59, "clutter": 3.02},
    "mean_altitude_m": {"drone": 117.0, "bird": 54.0, "clutter": 26.0},
    "heading_std_deg": {"drone": 3.8,  "bird": 27.4, "clutter": 40.6},
    "mean_rssi_dbm":   {"drone": -63.7, "bird": -80.9, "clutter": -90.9},
    "rssi_std":        {"drone": 2.04, "bird": 4.50, "clutter": 8.85},
}


def _format(feature: str, value: float) -> str:
    _label, unit, places = FEATURE_META.get(feature, (feature, "", 2))
    return f"{value:.{places}f}{unit}"


def _nearest_class(feature: str, value: float) -> str | None:
  
    reference = TYPICAL.get(feature)
    if not reference:
        return None
    return min(reference, key=lambda name: abs(value - reference[name]))


def build_statement(feature: str, value: float) -> str:
  
    label = FEATURE_META.get(feature, (feature, "", 2))[0]
    nearest = _nearest_class(feature, value)
    text = f"{label} is {_format(feature, value)}"

    if nearest:
        typical = _format(feature, TYPICAL[feature][nearest])
        text += f", closest to a typical {nearest} ({typical})"

    why = WHY.get(feature)
    return f"{text} — {why}." if why else f"{text}."


# --------------------------------------------------------------------------
# Forest decomposition
# --------------------------------------------------------------------------
def _node_probability(tree, node: int, class_index: int) -> float:

    counts = tree.value[node][0]
    total = counts.sum()
    return float(counts[class_index] / total) if total > 0 else 0.0


def forest_contributions(model, sample: list[float], class_index: int) -> list[float]:
  
    contributions = [0.0] * len(sample)
    trees = model.estimators_

    for estimator in trees:
        tree = estimator.tree_
        node = 0
        while tree.children_left[node] != -1:
            feature = int(tree.feature[node])
            before = _node_probability(tree, node, class_index)

            if sample[feature] <= tree.threshold[node]:
                node = int(tree.children_left[node])
            else:
                node = int(tree.children_right[node])

            contributions[feature] += _node_probability(tree, node, class_index) - before

    return [c / len(trees) for c in contributions]


def forest_bias(model, class_index: int) -> float:
    
    return sum(
        _node_probability(estimator.tree_, 0, class_index)
        for estimator in model.estimators_
    ) / len(model.estimators_)


def explain_forest(
    model, sample: list[float], label: str, top_n: int = 4
) -> list[dict]:
  
    classes = list(model.classes_)
    if label not in classes:
        return []

    index = classes.index(label)
    contributions = forest_contributions(model, sample, index)

    evidence = [
        {
            "feature": name,
            "label": FEATURE_META.get(name, (name, "", 2))[0],
            "value": round(value, 3),
            "display_value": _format(name, value),
            "contribution": round(contribution, 4),
            "direction": "supports" if contribution >= 0 else "opposes",
            "statement": build_statement(name, value),
        }
        for name, value, contribution in zip(FEATURE_NAMES, sample, contributions)
    ]

    evidence.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return evidence[:top_n]


def summarise(label: str, confidence: float, evidence: list[dict]) -> str:
    
    if not evidence:
        return f"Classified {label} at {confidence:.0%} confidence."

    supporting = [item for item in evidence if item["direction"] == "supports"][:2]
    if not supporting:
        return (
            f"Classified {label} at {confidence:.0%} confidence, but no single "
            "feature strongly supports it — treat this verdict as weak."
        )

    names = " and ".join(item["label"].lower() for item in supporting)
    return f"Classified {label} at {confidence:.0%} confidence, mainly on {names}."


# --------------------------------------------------------------------------
# Fallback for the rule-based classifier
# --------------------------------------------------------------------------
def explain_rule(sample: list[float], label: str) -> list[dict]:
    
    values = dict(zip(FEATURE_NAMES, sample))
    used = ["rssi_std", "mean_rssi_dbm", "heading_std_deg"]

    return [
        {
            "feature": name,
            "label": FEATURE_META.get(name, (name, "", 2))[0],
            "value": round(values[name], 3),
            "display_value": _format(name, values[name]),
            "contribution": 0.0,
            "direction": "supports" if _nearest_class(name, values[name]) == label else "opposes",
            "statement": build_statement(name, values[name]),
        }
        for name in used
        if name in values
    ]
