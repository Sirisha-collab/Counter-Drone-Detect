import argparse
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from .features import CLASS_LABELS, FEATURE_NAMES

RNG = np.random.default_rng(42)

# Mean / spread for each feature, per class, in FEATURE_NAMES order.

PROFILES: dict[str, list[tuple[float, float]]] = {
    #            speed         speed_std    altitude       turn         rssi         rssi_std
    "drone":   [(16.0, 5.5), (1.4, 0.5),  (120.0, 50.0), (5.0, 2.5),  (-58.0, 7.0),  (2.2, 0.9)],
    "bird":    [(9.5, 3.0),  (3.2, 1.1),  (55.0, 25.0),  (27.0, 8.0), (-78.0, 7.0),  (4.6, 1.6)],
    "clutter": [(4.5, 2.5),  (4.6, 1.6),  (25.0, 14.0),  (40.0, 12.0), (-87.0, 7.0), (9.2, 3.0)],
}


def synthesize_dataset(per_class: int = 1500) -> tuple[np.ndarray, np.ndarray]:
    rows, labels = [], []
    for label in CLASS_LABELS:
        profile = PROFILES[label]
        sample = np.column_stack(
            [RNG.normal(mean, spread, per_class) for mean, spread in profile]
        )
        # Physical sanity: nothing flies below the ground or turns > 180°.
        sample[:, 1] = np.clip(sample[:, 1], 0, None)   # speed_std
        sample[:, 2] = np.clip(sample[:, 2], 0, None)   # altitude
        sample[:, 3] = np.clip(sample[:, 3], 0, 180)    # turn rate
        sample[:, 5] = np.clip(sample[:, 5], 0, None)   # rssi_std
        rows.append(sample)
        labels += [label] * per_class
    return np.vstack(rows), np.array(labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the track classifier.")
    parser.add_argument("--samples", type=int, default=1500, help="samples per class")
    parser.add_argument("--out", default="models/classifier.joblib")
    args = parser.parse_args()

    X, y = synthesize_dataset(args.samples)
    print(f"Dataset: {X.shape[0]} rows x {X.shape[1]} features "
          f"across {len(CLASS_LABELS)} classes\n")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200, max_depth=12, min_samples_leaf=3, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print(classification_report(y_test, predictions, digits=3))
    print("Confusion matrix (rows = truth, columns = predicted)")
    print("labels:", list(model.classes_))
    print(confusion_matrix(y_test, predictions, labels=list(model.classes_)), "\n")

    print("Which features mattered most:")
    for name, weight in sorted(
        zip(FEATURE_NAMES, model.feature_importances_), key=lambda p: -p[1]
    ):
        print(f"  {name:<20} {weight:.3f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    import joblib

    joblib.dump(
        {"model": model, "labels": list(model.classes_), "features": FEATURE_NAMES}, out
    )
    print(f"\nSaved to {out.resolve()}")


if __name__ == "__main__":
    main()
