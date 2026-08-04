import argparse
from collections import defaultdict

from ..simulator import DroneSimulator
from .feature_catalog import CHANNELS, FEATURE_SPECS, extract_all

CLASSES = ["drone", "bird", "clutter"]


def collect(ticks: int, sims: int, min_reports: int = 8) -> dict[str, list[dict]]:

    by_class: dict[str, list[dict]] = defaultdict(list)

    for _ in range(sims):
        simulator = DroneSimulator(realtime=False)
        history: dict[str, list[dict]] = defaultdict(list)
        truth: dict[str, str] = {}

        for _ in range(ticks):
            detections, _departed = simulator.tick()
            for detection in detections:
                tid = detection["track_id"]
                history[tid].append(detection)
                truth[tid] = detection["ground_truth"]

        for tid, samples in history.items():
            if len(samples) >= min_reports:
                by_class[truth[tid]].append(extract_all(samples[-20:]))

    return by_class


def f_score(values_by_class: dict[str, list[float]]) -> float:

    groups = [v for v in values_by_class.values() if len(v) > 1]
    if len(groups) < 2:
        return 0.0

    total_n = sum(len(g) for g in groups)
    grand_mean = sum(sum(g) for g in groups) / total_n

    between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in groups)
    within = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)

    k = len(groups)
    if within <= 1e-12 or total_n - k <= 0:
        return 0.0
    return (between / (k - 1)) / (within / (total_n - k))


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank features by separability.")
    parser.add_argument("--ticks", type=int, default=1500)
    parser.add_argument("--sims", type=int, default=20)
    args = parser.parse_args()

    print(f"Collecting from {args.sims} runs x {args.ticks} ticks...\n")
    by_class = collect(args.ticks, args.sims)
    for name in CLASSES:
        print(f"  {name:<8} {len(by_class[name]):>4} tracks")

    scored = []
    for feature in FEATURE_SPECS:
        per_class = {c: [row[feature] for row in by_class[c]] for c in CLASSES}
        scored.append((f_score(per_class), feature, {c: sum(v) / len(v) for c, v in per_class.items() if v}))
    scored.sort(reverse=True)

    print(f"\n{'feature':<24}{'channel':<10}{'drone':>10}{'bird':>10}{'clutter':>10}{'F':>10}")
    print("-" * 74)
    for score, feature, means in scored:
        channel = FEATURE_SPECS[feature][0]
        print(
            f"{feature:<24}{channel:<10}"
            f"{means.get('drone', 0):>10.2f}{means.get('bird', 0):>10.2f}"
            f"{means.get('clutter', 0):>10.2f}{score:>10.1f}"
        )

    print("\nBy channel, best feature in each:")
    for channel, features in CHANNELS.items():
        best = max((s for s, f, _ in scored if f in features), default=0.0)
        winner = next(f for s, f, _ in scored if f in features and s == best)
        print(f"  {channel:<10} {winner:<24} F={best:.1f}")


if __name__ == "__main__":
    main()
