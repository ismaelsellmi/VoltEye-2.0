// Fond de l'application : un écran de mesure. Aurore bleue et jaune, graticule d'oscilloscope et,
// en filigrane, les trois phases du courant (décalées de 120°). Un point de mesure jaune parcourt la phase 1.
const W = 2400;
const H = 320;
const A = 96;
const P = 1000;

function phase(shift: number) {
  let d = "";
  for (let x = 0; x <= W; x += 10) {
    const y = H / 2 - A * Math.sin((2 * Math.PI * x) / P + shift);
    d += `${x ? "L" : "M"}${x},${y.toFixed(1)}`;
  }
  return d;
}

const PHASES = [phase(0), phase((2 * Math.PI) / 3), phase((4 * Math.PI) / 3)];

export function Backdrop() {
  return (
    <div aria-hidden className="backdrop">
      <div className="graticule" />
      <svg className="wave" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="phase-1" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="var(--accent)" stopOpacity="0" />
            <stop offset="0.25" stopColor="var(--accent)" />
            <stop offset="0.75" stopColor="var(--accent)" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="phase-2" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="var(--signal)" stopOpacity="0" />
            <stop offset="0.5" stopColor="var(--signal)" />
            <stop offset="1" stopColor="var(--signal)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="phase-3" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="var(--m-convoyeur)" stopOpacity="0" />
            <stop offset="0.5" stopColor="var(--m-convoyeur)" />
            <stop offset="1" stopColor="var(--m-convoyeur)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={PHASES[1]} stroke="url(#phase-2)" strokeWidth={1.25} opacity={0.6} />
        <path d={PHASES[2]} stroke="url(#phase-3)" strokeWidth={1.25} opacity={0.55} />
        <path d={PHASES[0]} stroke="url(#phase-1)" strokeWidth={1.75} />
        <path className="wave-pulse" d={PHASES[0]} stroke="var(--signal)" strokeWidth={3.5} pathLength={1} />
      </svg>
    </div>
  );
}
