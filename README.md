A dashboard for a simulated passive counter-UAS sensor.

## Explainable evidence

Every classification now says why. ml/explain.py decomposes a random-forest prediction along the decision path each track takes through all 200 trees, 
so bias + sum(contributions) = predicted probability exactly (verified to 4e-16). 

25 features across 7 channels, each with its unit, definition, and reason.
`analyze_features.py` ranks them by ANOVA F-score against the simulator.

## Toolchain

React 19, Vite 7, Tailwind CSS v4, react-leaflet 5. Tailwind v4 

## Screenshots

DASHBOARD
<img width="1913" height="958" alt="Screenshot 2026-08-04 112413" src="https://github.com/user-attachments/assets/56e92976-1285-4034-a333-7e818445e0c5" />

<img width="1805" height="787" alt="Screenshot 2026-08-04 112435" src="https://github.com/user-attachments/assets/49330c1a-f107-4a6a-adf5-2b342f7c7f5e" />

