interface Props {
  /** Outer diameter in px. */
  size: number;
  /** Distance from the wrapper edge to the glowing core. */
  inset?: number;
  /** Expanding rings; 0 renders a still orb. */
  rings?: 0 | 1 | 2;
  /** Ring cadence in seconds. */
  speed?: number;
  /** Dark-background treatment used on the live-call screen. */
  night?: boolean;
}

export default function Orb({ size, inset = Math.round(size * 0.14), rings = 2, speed = 2.6, night }: Props) {
  return (
    <div
      className={`orb${night ? ' night' : ''}${rings === 0 ? ' quiet' : ''}`}
      style={{ width: size, height: size }}
    >
      {rings >= 1 && <div className="ring" style={{ animationDuration: `${speed}s` }} />}
      {rings >= 2 && (
        <div className="ring b" style={{ animationDuration: `${speed}s`, animationDelay: `${speed / 2}s` }} />
      )}
      <div className="core" style={{ inset }} />
    </div>
  );
}
