import logo from "../data/logo.json";

/** Symbole VoltEye : un œil tracé par une période de courant, la pupille jaune est le point de mesure.
 *  Couleur du trait : currentColor (s'adapte au thème) ; pupille : jaune signal.
 *  `animated` : l'axe se trace, les paupières se dessinent, puis la pupille s'allume (1,6 s).
 *  `live` : la pupille respire tant que le compteur est en direct. */
export function LogoMark({ className = "", animated = false, live = false, simple = false, title }: { className?: string; animated?: boolean; live?: boolean; simple?: boolean; title?: string }) {
  const lid = simple ? 10 : logo.paupiere;
  const axisW = simple ? 7 : logo.axe_epaisseur;
  const r = simple ? 15 : logo.pupille;
  const [x1, x2] = simple ? [10, 110] : logo.axe;
  const paths = simple ? logo.simple : logo;
  return (
    <svg
      viewBox={logo.viewBox}
      className={`${animated ? "logo-draw" : ""} ${live ? "logo-live" : ""} ${className}`}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
        <line className="logo-axis" x1={x1} y1={logo.cy} x2={x2} y2={logo.cy} strokeWidth={axisW} pathLength={1} />
        <path className="logo-lid" d={paths.haut} strokeWidth={lid} pathLength={1} />
        <path className="logo-lid logo-lid-lo" d={paths.bas} strokeWidth={lid} pathLength={1} />
      </g>
      <circle className="logo-pupil" cx="60" cy={logo.cy} r={r} fill="var(--signal)" />
    </svg>
  );
}

/** Écran de chargement : le symbole s'allume comme un instrument. */
export function BrandLoader({ full = true }: { full?: boolean }) {
  return (
    <div className={`grid place-items-center ${full ? "min-h-dvh" : "min-h-[50vh]"}`} role="status">
      <LogoMark animated className="w-32 text-ink" />
      <span className="sr-only">Chargement de VoltEye</span>
    </div>
  );
}
