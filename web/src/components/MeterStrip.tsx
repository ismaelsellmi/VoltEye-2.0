import { Link } from "react-router-dom";
import { useMemo } from "react";
import { useLive, type LinkState } from "../lib/live";
import { MACHINES } from "../lib/machines";
import { nf } from "../lib/format";
import { useResolvedTheme, token } from "../lib/theme";

const STATE_TEXT: Record<LinkState, string> = {
  connexion: "Connexion…",
  "en direct": "En direct",
  muet: "Passerelle muette",
  "hors ligne": "Hors ligne",
};

/** Signature de l'application : le compteur unique, et sous sa courbe, les machines qu'il contient.
 *  5 dernières minutes, puissance estimée de chaque machine empilée sous la mesure totale. */
export function MeterStrip({ compact = false }: { compact?: boolean }) {
  const { measures, state, last } = useLive();
  useResolvedTheme();
  const W = 600;
  const H = compact ? 32 : 44;
  const recent = measures.slice(-300);

  const paths = useMemo(() => {
    if (recent.length < 2) return null;
    const max = Math.max(10, ...recent.map((m) => m.p_kw)) * 1.08;
    const x = (i: number) => (i / (recent.length - 1)) * W;
    const y = (v: number) => H - (v / max) * H;
    const layers: { m: string; d: string }[] = [];
    const acc = new Array(recent.length).fill(0);
    for (const m of MACHINES) {
      const lo = acc.slice();
      recent.forEach((r, i) => (acc[i] += r.estime?.[m] ?? 0));
      if (acc.every((v, i) => v === lo[i])) continue;
      const top = acc.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
      const bottom = lo.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse();
      layers.push({ m, d: `M${top.join("L")}L${bottom.join("L")}Z` });
    }
    const total = "M" + recent.map((r, i) => `${x(i).toFixed(1)},${y(r.p_kw).toFixed(1)}`).join("L");
    return { layers, total };
  }, [recent, H]);

  const live = state === "en direct";
  return (
    <Link to="/direct" className="group flex min-w-0 flex-1 items-center justify-end gap-3 rounded-xl px-2 py-1 transition-colors hover:bg-module-2" aria-label={`Ouvrir le direct : ${last ? `${nf(last.p_kw, 1)} kW` : "pas de mesure"}, ${STATE_TEXT[state].toLowerCase()}`}>
      <div className="hidden min-w-0 flex-1 sm:block">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block w-full" style={{ height: H }} aria-hidden>
          <line x1="0" x2={W} y1={H - 0.5} y2={H - 0.5} stroke={token("--edge")} />
          {paths?.layers.map((l) => (
            <path key={l.m} d={l.d} fill={`var(--m-${l.m})`} opacity={0.78} />
          ))}
          {paths && <path d={paths.total} fill="none" stroke="var(--ink)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />}
        </svg>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className="flex items-center gap-1.5 rounded-full border border-edge bg-module-2 p-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-ink-2 min-[480px]:px-2 min-[480px]:py-1">
          <span aria-hidden className={`inline-block h-2 w-2 rounded-full ${live ? "live-dot bg-signal" : state === "hors ligne" ? "bg-critical" : "bg-ink-3"}`} />
          <span className="hidden min-[480px]:inline">{STATE_TEXT[state]}</span>
        </span>
        <span className="reading text-[30px] sm:text-[34px]">
          {last ? nf(last.p_kw, 1) : "–"}
          <span className="ml-1 font-sans text-sm font-semibold tracking-normal text-ink-3">kW</span>
        </span>
      </div>
    </Link>
  );
}
