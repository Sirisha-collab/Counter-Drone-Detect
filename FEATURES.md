# Feature reference

What the sensor gives you, what we compute from it, and how well each thing
works. Every number in this document was measured by running
`python -m app.ml.analyze_features` against the simulator — nothing here is
asserted from intuition.

---

## 1. The distinction that matters: channels vs features

A sensor report has six raw **channels**:

| Channel | Field | What the sensor is telling you |
|---|---|---|
| Range | `distance_m` | How far away |
| Bearing | `bearing_deg` | Which compass direction, from us |
| Heading | `heading_deg` | Which way it is pointing |
| Speed | `speed_mps` | How fast |
| Altitude | `altitude_m` | How high |
| RF | `rssi_dbm` | How loud its radio signal is |

None of these is a feature. "The object is 1,204 m away" says nothing about
what the object *is* — move the sensor 500 m and the number changes while the
object does not.

A **feature** is computed *across a window of reports*: a rate, a spread, a
ratio, a correlation. The test for a good one:

> Does it stay the same when you move the sensor, and change when you swap
> the object?

`mean_range_m` fails that test badly, which is why it scores F=88 while
`turn_rate_dps` scores F=2402.

---

## 2. The full catalog

25 features across 7 channels. Implementation: `app/ml/feature_catalog.py`.
Every entry carries its channel, unit, definition, and reason in
`FEATURE_SPECS`, so the code and this document cannot drift apart.

### Range channel

| Feature | Unit | Definition |
|---|---|---|
| `closing_rate_mps` | m/s | Mean rate of approach. Positive means inbound. |
| `closing_rate_std` | m/s | Spread of that rate — steady approach vs drifting. |
| `min_range_m` | m | Closest approach so far. |
| `mean_range_m` | m | Average distance. Context only. |

### Bearing channel

| Feature | Unit | Definition |
|---|---|---|
| `bearing_rate_dps` | deg/s | Mean absolute change in bearing. |
| `cross_range_speed_mps` | m/s | Bearing rate in rad/s × range — tangential velocity. |
| `bearing_span_deg` | deg | Total angular sweep, measured wrap-aware. |

### Heading channel

| Feature | Unit | Definition |
|---|---|---|
| `turn_rate_dps` | deg/s | Mean absolute heading change per second. |
| `turn_rate_std` | deg/s | Spread of the turn rate. |
| `straightness` | 0–1 | Net displacement ÷ total path length. |
| `heading_reversals` | count | How often turn direction flips sign. |

### Speed channel

| Feature | Unit | Definition |
|---|---|---|
| `mean_speed_mps` | m/s | Average ground speed. |
| `speed_std_mps` | m/s | Spread of speed. |
| `speed_cv` | ratio | Speed spread ÷ mean speed. Scale-free. |
| `max_speed_mps` | m/s | Fastest report in the window. |

### Altitude channel

| Feature | Unit | Definition |
|---|---|---|
| `mean_altitude_m` | m | Average height. |
| `altitude_std_m` | m | Spread of height. |
| `climb_rate_mps` | m/s | Mean absolute vertical rate. |

### RF channel

| Feature | Unit | Definition |
|---|---|---|
| `mean_rssi_dbm` | dBm | Average signal strength. |
| `rssi_std_db` | dB | Spread of signal strength. |
| `rssi_corrected_dbm` | dBm | Signal with expected path loss added back. |
| `rssi_corrected_std` | dB | Spread of the corrected signal. |
| `rssi_range_corr` | −1…1 | Correlation between signal and log range. |

### Track quality

| Feature | Unit | Definition |
|---|---|---|
| `n_reports` | count | How many detections accumulated. |
| `track_duration_s` | s | Age of the track. |

These last two say nothing about the object. They tell you how much to trust
everything above.

---

## 3. Measured separability

From 20-report windows across 375 tracks. **F** is a one-way ANOVA statistic:
between-class spread over within-class spread. Higher means the three classes
overlap less along that one feature alone.

| Feature | Channel | Drone | Bird | Clutter | F |
|---|---|---:|---:|---:|---:|
| `rssi_corrected_dbm` | rf | −57.36 | −78.10 | −86.72 | **9062** |
| `mean_rssi_dbm` | rf | −63.66 | −80.92 | −90.88 | 2687 |
| `turn_rate_dps` | heading | 1.91 | 13.69 | 20.28 | 2402 |
| `turn_rate_std` | heading | 1.39 | 9.83 | 14.37 | 2160 |
| `rssi_corrected_std` | rf | 2.00 | 4.49 | 8.86 | 2122 |
| `rssi_std_db` | rf | 2.04 | 4.50 | 8.85 | 2089 |
| `climb_rate_mps` | altitude | 0.94 | 2.19 | 2.55 | 920 |
| `speed_cv` | speed | 0.08 | 0.32 | 0.65 | 575 |
| `altitude_std_m` | altitude | 2.53 | 5.92 | 6.83 | 513 |
| `straightness` | heading | 0.99 | 0.64 | 0.50 | 477 |
| `speed_std_mps` | speed | 1.15 | 2.59 | 3.02 | 408 |
| `closing_rate_mps` | range | −15.31 | −1.78 | −0.60 | 360 |
| `mean_altitude_m` | altitude | 116.93 | 54.06 | 26.13 | 241 |
| `closing_rate_std` | range | 1.22 | 4.67 | 3.74 | 218 |
| `mean_speed_mps` | speed | 15.88 | 9.25 | 5.36 | 218 |
| `cross_range_speed_mps` | bearing | 1.94 | 5.75 | 3.34 | 173 |
| `mean_range_m` | range | 2658 | 1806 | 2029 | 88 |
| `max_speed_mps` | speed | 18.02 | 14.15 | 11.52 | 69 |
| `bearing_rate_dps` | bearing | 0.05 | 0.25 | 0.11 | 50 |
| `min_range_m` | range | 2362 | 1710 | 1983 | 47 |
| `bearing_span_deg` | bearing | 1.63 | 6.88 | 2.60 | 31 |
| `rssi_range_corr` | rf | −0.19 | −0.04 | −0.03 | 20 |
| `track_duration_s` | quality | 37.82 | 38.00 | 37.87 | 0.5 |
| `n_reports` | quality | 19.91 | 20.00 | 19.94 | 0.5 |
| `heading_reversals` | heading | 9.02 | 8.92 | 9.04 | **0.1** |

---

## 4. Reading the table

### Range correction is worth 3.4× (F 2687 → 9062)

The best feature in the catalog and the second-best are the same measurement.
The difference is one line of arithmetic:

```python
corrected = rssi_dbm + PATH_LOSS_DB_PER_DECADE * math.log10(range_km)
```

Raw `mean_rssi_dbm` conflates two things — how powerful the emitter is, and
how far away it is. A quiet bird up close can read louder than a noisy drone
far away, so the classes smear into each other.

Adding the expected path loss back estimates what the emitter would measure at
a fixed 1 km reference. The same drone at 500 m and at 3 km now produces the
same number. The classes stop overlapping and F more than triples.

**The general lesson:** if you know the physics that contaminates a
measurement, undo it before handing it to the model. The model *can* learn to
undo it, but only by spending capacity it should be spending elsewhere.

### Rates and spreads beat levels

Look at where the raw averages sit. `mean_speed_mps` scores 218.
`mean_range_m` scores 88. `mean_altitude_m` scores 241.

Now look at the derived quantities. `turn_rate_dps` scores 2402. `speed_cv`
scores 575 — eleven times better than its own parent `mean_speed_mps` — purely
because dividing spread by mean makes it scale-free.

A drone holds its commanded speed within 8% (`speed_cv` 0.08). Clutter varies
by 65%. That ratio is the same whether the object is doing 5 m/s or 25 m/s,
which is exactly what makes it a good feature.

### Three features are dead weight

`heading_reversals` (F=0.1), `n_reports` (0.5), `track_duration_s` (0.5).

`heading_reversals` was my hypothesis that jitter would flip turn direction
more often than deliberate manoeuvring. The data says all three classes reverse
about nine times per twenty reports. The hypothesis was wrong — the
*magnitude* of the turns differs, not how often they change sign, and
`turn_rate_dps` already captures magnitude.

`n_reports` and `track_duration_s` scoring nothing is *correct and expected*.
They are windowed to a fixed length, so of course they are identical across
classes. They exist to gate confidence, not to classify.

**Delete features that score near zero.** They cost compute and give the model
one more axis to overfit on.

### One feature underperformed its theory

`rssi_range_corr` (F=20) should be excellent. A genuine emitter obeys the
inverse-distance law, so its signal should correlate near −1 with log range.
Measured: −0.19 for drones, −0.03 for clutter. The direction is right, the
magnitude is far too weak.

The reason is window length. Over 20 reports a drone covers about 600 m, so
`log10(range_km)` barely moves and the correlation is computed over almost no
dynamic range. Widen the window to 60 reports and this feature should sharpen
considerably. Worth testing.

### Straightness is the best-behaved feature

`straightness` (F=477) is net displacement divided by path length. A drone
scores 0.99 — it flies where it is pointing. Clutter scores 0.50.

It is dimensionless, unaffected by speed, range, or units, and needs no
calibration constant. If you had to port this model to a different sensor with
different scaling, `straightness` would survive the move unchanged while
`rssi_corrected_dbm` would need its path-loss constant recalibrated first.

---

## 5. Which six the model actually uses

`app/ml/features.py` ships a six-feature subset, chosen before this analysis
existed. Comparing it against the catalog:

| Shipped feature | Catalog F | Verdict |
|---|---:|---|
| `mean_rssi_dbm` | 2687 | Keep, but `rssi_corrected_dbm` is 3.4× better |
| `rssi_std` | 2089 | Keep |
| `heading_std_deg` | ≈2402 | Keep — the second-strongest signal |
| `speed_std` | 408 | Superseded by `speed_cv` at F=575 |
| `mean_speed_mps` | 218 | Marginal |
| `mean_altitude_m` | 241 | Marginal |

A better six, on this evidence:

```python
FEATURE_NAMES = [
    "rssi_corrected_dbm",   # F 9062
    "turn_rate_dps",        # F 2402
    "rssi_corrected_std",   # F 2122
    "climb_rate_mps",       # F  920
    "speed_cv",             # F  575
    "straightness",         # F  477
]
```

**Do not swap these in blind.** F-score ranks features *individually*. Two
features that both score 2000 may be measuring the same underlying thing —
`rssi_std_db` (2089) and `rssi_corrected_std` (2122) are nearly identical
columns, and including both adds redundancy, not information. Check the
correlation between candidates before committing, and validate end to end.

---

## 6. Real multi-sensor systems

This project has one simulated sensor producing kinematics plus RSSI. A real
installation fuses several, each contributing different features:

| Sensor | Raw output | Typical features |
|---|---|---|
| RF receiver | Spectrum over time | Occupied bandwidth, hop rate and pattern, protocol signature, burst duty cycle |
| Radar | Range-Doppler returns | Micro-Doppler from rotor blades, radar cross-section, RCS fluctuation rate |
| EO/IR camera | Image frames | Silhouette aspect ratio, wingbeat frequency, thermal signature, apparent size vs range |
| Acoustic array | Waveform | Rotor harmonic spacing, blade-pass frequency, sound pressure vs range |

The rotor-blade features are the interesting ones — a spinning propeller
produces a periodic modulation that birds physically cannot generate. That is
the closest thing to a definitive drone signature, and it is the main reason
real systems bother with radar or acoustics at all.

Adding any of these to this project means extending the simulator to emit a new
channel. The pipeline downstream — tracker, feature extraction, classifier,
dashboard — would not need to change.

---

## 7. Reproducing this

```bash
cd backend
python -m app.ml.analyze_features --ticks 1500 --sims 20
```

Prints the per-class means and F-scores above. Numbers will move by a few
percent between runs; the ranking is stable.

**One thing that will bite you.** The simulator must be constructed with
`realtime=False` for offline analysis:

```python
simulator = DroneSimulator(realtime=False)
```

In live operation the loop genuinely sleeps two seconds between ticks, so
wall-clock timestamps are correct. Offline it runs thousands of ticks back to
back, so wall-clock stamps land microseconds apart — and every feature that
divides by elapsed time inflates by roughly 20,000×. The first run of this
analysis reported a turn rate of 3,812 deg/s before that was caught.

Any feature computed as a *rate* is vulnerable to this class of bug, and the
symptom is a plausible-looking number in a column you weren't checking.
Sanity-check units. A drone turning at 1.91 deg/s is believable; at 3,812
deg/s it is completing ten full rotations per second.
