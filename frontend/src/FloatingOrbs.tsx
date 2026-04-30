export function FloatingOrbs() {
  return (
    <div className="floating-orbs" aria-hidden>
      {Array.from({ length: 12 }, (_, i) => (
        <span key={i} className="orb" />
      ))}
    </div>
  );
}
