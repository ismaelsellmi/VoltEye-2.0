import type { EChartsCoreOption } from "echarts/core";
import { token } from "./theme";

/** Couleurs du thème courant, résolues pour le canvas. */
export function palette() {
  return {
    ink: token("--ink"),
    ink2: token("--ink-2"),
    ink3: token("--ink-3"),
    grid: token("--grid"),
    module: token("--surface"),
    glass: token("--module-strong"),
    glassBorder: token("--glass-border"),
    shadow: token("--shadow"),
    edge: token("--edge"),
    accent: token("--accent"),
    signal: token("--signal"),
    good: token("--good"),
    warning: token("--warning"),
    critical: token("--critical"),
    m: (k: string) => token(`--m-${k}`),
  };
}
export type Palette = ReturnType<typeof palette>;

export const FONT_SANS = "Manrope Variable";
export const FONT_MONO = "IBM Plex Mono";

/** Remplissage dégradé sous une courbe : la couleur de la série qui s'efface vers l'axe. */
export function fade(hex: string, top = 0.28) {
  const n = parseInt(hex.replace("#", "").slice(0, 6), 16);
  const rgb = `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
  return {
    type: "linear",
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: `rgba(${rgb}, ${top})` },
      { offset: 1, color: `rgba(${rgb}, 0)` },
    ],
  };
}

/** Réglages communs : axes et grille discrets, infobulle en verre au survol, typographie de l'interface. */
export function base(p: Palette): EChartsCoreOption {
  const axis = {
    axisLine: { lineStyle: { color: p.edge } },
    axisTick: { show: false },
    axisLabel: { color: p.ink3, fontFamily: FONT_MONO, fontSize: 11 },
    splitLine: { lineStyle: { color: p.grid } },
    nameTextStyle: { color: p.ink3, fontFamily: FONT_MONO, fontSize: 11 },
  };
  return {
    backgroundColor: "transparent",
    animationDuration: 700,
    animationEasing: "cubicOut",
    animationDurationUpdate: 450,
    textStyle: { fontFamily: FONT_SANS, color: p.ink2 },
    grid: { left: 8, right: 16, top: 44, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: p.glass,
      borderColor: p.glassBorder,
      borderWidth: 1,
      padding: [10, 12],
      extraCssText: `backdrop-filter: blur(16px) saturate(170%); -webkit-backdrop-filter: blur(16px) saturate(170%); border-radius: 14px; box-shadow: 0 16px 40px -16px ${p.shadow};`,
      textStyle: { color: p.ink, fontFamily: FONT_SANS, fontSize: 13 },
      axisPointer: { type: "line", lineStyle: { color: p.ink3, type: "dashed" } },
    },
    legend: { type: "scroll", top: 0, left: 0, right: 0, itemGap: 18, icon: "circle", pageTextStyle: { color: p.ink3 }, pageIconColor: p.ink2, pageIconInactiveColor: p.edge, itemWidth: 9, itemHeight: 9, textStyle: { color: p.ink2, fontSize: 12, fontFamily: FONT_SANS, fontWeight: 600 } },
    xAxis: axis,
    yAxis: axis,
    aria: { enabled: true },
  };
}
