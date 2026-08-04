import argparse
import random
from collections import defaultdict
from pathlib import Path

from ..simulator import DroneSimulator
from .features import CLASS_LABELS
from .sequence import SEQ_CHANNELS, SEQ_LEN, build_sequence

#collects sequences, labels, and track_ids from simulator runs
#One simulator only holds nine objects at a time
def harvest(ticks: int, sims: int = 8, stride: int = 3) -> tuple[list, list, list]:

    sequences: list[list[list[float]]] = []
    labels: list[str] = []
    track_ids: list[str] = []

    for _ in range(sims):
        simulator = DroneSimulator(realtime=False)
        history: dict[str, list[dict]] = defaultdict(list)
        since_kept: dict[str, int] = defaultdict(int)

        for _ in range(ticks):
            detections, _departed = simulator.tick()
            for detection in detections:
                tid = detection["track_id"]
                history[tid].append(detection)
                if len(history[tid]) < 6:
                    continue

                since_kept[tid] += 1
                if since_kept[tid] < stride:
                    continue
                since_kept[tid] = 0

                steps = build_sequence(history[tid])
                if steps:
                    sequences.append(steps)
                    labels.append(detection["ground_truth"])
                    track_ids.append(tid)

    return sequences, labels, track_ids


def split_by_track(
    sequences: list, labels: list, track_ids: list, holdout: float = 0.25
):

    unique = sorted(set(track_ids))
    random.Random(42).shuffle(unique)
    cut = int(len(unique) * (1 - holdout))
    train_tracks = set(unique[:cut])

    train_idx = [i for i, t in enumerate(track_ids) if t in train_tracks]
    test_idx = [i for i, t in enumerate(track_ids) if t not in train_tracks]

    pick = lambda source, idx: [source[i] for i in idx]  # noqa: E731
    return (
        pick(sequences, train_idx),
        pick(labels, train_idx),
        pick(sequences, test_idx),
        pick(labels, test_idx),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GRU track classifier.")
    parser.add_argument("--ticks", type=int, default=1500, help="ticks per simulator run")
    parser.add_argument("--sims", type=int, default=24, help="independent simulator runs")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=2e-3)
    parser.add_argument("--hidden", type=int, default=48)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--out", default="models/classifier_gru.pt")
    args = parser.parse_args()

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    from .torch_classifier import build_network

    torch.manual_seed(42)

    print(f"Harvesting {args.sims} runs x {args.ticks} ticks...")
    sequences, labels, track_ids = harvest(args.ticks, args.sims)
    print(
        f"  {len(sequences)} windows from {len(set(track_ids))} tracks, "
        f"each {SEQ_LEN} steps x {len(SEQ_CHANNELS)} channels"
    )
    for label in CLASS_LABELS:
        print(f"    {label:<8} {labels.count(label):>6}")

    train_x, train_y, test_x, test_y = split_by_track(sequences, labels, track_ids)
    print(f"\nSplit by track: {len(train_x)} train windows, {len(test_x)} test windows")
    if not test_x:
        raise SystemExit("No test windows — run with more --ticks.")

    label_index = {name: i for i, name in enumerate(CLASS_LABELS)}
    to_tensor = lambda xs, ys: TensorDataset(  # noqa: E731
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor([label_index[y] for y in ys], dtype=torch.long),
    )

    train_loader = DataLoader(
        to_tensor(train_x, train_y), batch_size=args.batch_size, shuffle=True
    )
    test_set = to_tensor(test_x, test_y)

    model = build_network(len(CLASS_LABELS), args.hidden, args.layers)
    total = sum(p.numel() for p in model.parameters())
    print(f"Model: {total:,} parameters\n")

    # Class weights, because the profile mix is deliberately uneven.
    counts = torch.tensor(
        [max(1, train_y.count(name)) for name in CLASS_LABELS], dtype=torch.float32
    )
    criterion = nn.CrossEntropyLoss(weight=counts.sum() / (len(CLASS_LABELS) * counts))
    optimiser = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for batch_x, batch_y in train_loader:
            optimiser.zero_grad()
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            running += loss.item() * len(batch_y)

        model.eval()
        with torch.no_grad():
            predictions = model(test_set.tensors[0]).argmax(dim=1)
            accuracy = (predictions == test_set.tensors[1]).float().mean().item()
        if epoch % 5 == 0 or epoch == 1:
            print(
                f"  epoch {epoch:>3}  loss {running / len(train_x):.4f}  "
                f"held-out accuracy {accuracy:.3f}"
            )

    # --- per-class report ------------------------------------------------
    print("\nConfusion matrix (rows = truth, columns = predicted)")
    print("labels:", CLASS_LABELS)
    matrix = [[0] * len(CLASS_LABELS) for _ in CLASS_LABELS]
    with torch.no_grad():
        predictions = model(test_set.tensors[0]).argmax(dim=1)
    for truth, guess in zip(test_set.tensors[1].tolist(), predictions.tolist()):
        matrix[truth][guess] += 1
    for name, row in zip(CLASS_LABELS, matrix):
        support = sum(row) or 1
        print(f"  {name:<8} {row}   recall {row[CLASS_LABELS.index(name)] / support:.3f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "labels": CLASS_LABELS,
            "channels": SEQ_CHANNELS,
            "seq_len": SEQ_LEN,
            "hidden": args.hidden,
            "layers": args.layers,
        },
        out,
    )
    print(f"\nSaved to {out.resolve()}")
    print(
        "\nTraining and testing both come from the same simulator, "
        "so it measures how well the model learned this simulator "
    )


if __name__ == "__main__":
    main()
