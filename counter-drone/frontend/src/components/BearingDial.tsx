interface BearingDialProps {
  /** Where the contact sits, in degrees from the sensor site. */
  bearing: number;
  /** How far out, as a fraction of coverage (0 = on top of us, 1 = edge). */
  rangeFraction: number;
  color: string;
  size?: number;
}


export function BearingDial({
  bearing,
  rangeFraction,
  color,
  size = 30,
}: BearingDialProps) {
  const half = size / 2;
  const usable = half - 4;
  const radius = Math.max(2.5, Math.min(1, rangeFraction) * usable);

  // SVG y grows downward, so north is -y.
  const radians = ((bearing - 90) * Math.PI) / 180;
  const x = half + radius * Math.cos(radians);
  const y = half + radius * Math.sin(radians);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`Bearing ${Math.round(bearing)} degrees`}
      className="shrink-0"
    >
      <circle cx={half} cy={half} r={usable} fill="none" stroke="#D8DFE8" strokeWidth="1" />
      <circle
        cx={half}
        cy={half}
        r={usable * 0.5}
        fill="none"
        stroke="#D8DFE8"
        strokeWidth="0.75"
        strokeDasharray="1.5 2.5"
      />

      <line
        x1={half}
        y1={half - usable}
        x2={half}
        y2={half - usable + 3.5}
        stroke="#8A97A8"
        strokeWidth="1"
      />
      <circle cx={half} cy={half} r="1.4" fill="#0A7EA4" />
      <line
        x1={half}
        y1={half}
        x2={x}
        y2={y}
        stroke={color}
        strokeWidth="1"
        strokeOpacity="0.45"
      />
      <circle cx={x} cy={y} r="2.6" fill={color} />
    </svg>
  );
}
