const BARS = Array.from({ length: 22 }, (_, i) => ({
  height: 14 + Math.round(28 * Math.abs(Math.sin(i * 1.7))),
  duration: 0.35 + (i % 5) * 0.09,
  delay: (i % 7) * 0.07,
}));

/** Decorative level meter shown while the mic is hot. */
export default function Waveform() {
  return (
    <div className="waveform" aria-hidden>
      {BARS.map((bar, i) => (
        <i
          key={i}
          style={{
            height: bar.height,
            animation: `echoBar ${bar.duration}s ease-in-out ${bar.delay}s infinite alternate`,
          }}
        />
      ))}
    </div>
  );
}
