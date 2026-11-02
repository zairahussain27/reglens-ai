type Props = { value: number | null; size?: number; label?: string };

/** 270° gauge. Uses only the brand palette: orange fill, dark-orange when the score is low. */
export function ScoreGauge({ value, size = 168, label = "Compliance score" }: Props) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * 0.75;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const tone = value == null ? "empty" : pct < 40 ? "low" : "ok";
  const common = { cx: 60, cy: 60, r: radius, fill: "none", transform: "rotate(135 60 60)" } as const;
  return (
    <figure className={`gauge gauge--${tone}`} style={{ width: size }} role="img"
      aria-label={value == null ? `${label}: not scored` : `${label}: ${Math.round(pct)} percent`}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle {...common} className="gauge-track" strokeDasharray={`${arc} ${circumference}`} />
        {value != null && <circle {...common} className="gauge-fill" strokeDasharray={`${(arc * pct) / 100} ${circumference}`} />}
      </svg>
      <div className="gauge-value">
        <strong>{value == null ? "—" : Math.round(pct)}{value != null && <small>%</small>}</strong>
        <span>{label}</span>
      </div>
    </figure>
  );
}