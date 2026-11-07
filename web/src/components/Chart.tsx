import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, CustomChart, HeatmapChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,
  DataZoomComponent,
  VisualMapComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { token, useResolvedTheme } from "../lib/theme";

echarts.use([
  BarChart, LineChart, CustomChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent,
  MarkAreaComponent, MarkPointComponent, DataZoomComponent, VisualMapComponent, AriaComponent, CanvasRenderer,
]);

/** Couleurs du thème courant, résolues pour le canvas. */
export function palette() {
  return {
    ink: token("--ink"),
    ink2: token("--ink-2"),
    ink3: token("--ink-3"),
    grid: token("--grid"),
    module: token("--module"),
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

/** Réglages communs : axes et grille discrets, infobulle au survol, typographie de l'interface. */
export function base(p: Palette): EChartsCoreOption {
  const axis = {
    axisLine: { lineStyle: { color: p.edge } },
    axisTick: { show: false },
    axisLabel: { color: p.ink3, fontFamily: "IBM Plex Mono", fontSize: 11 },
    splitLine: { lineStyle: { color: p.grid } },
    nameTextStyle: { color: p.ink3, fontFamily: "IBM Plex Mono", fontSize: 11 },
  };
  return {
    backgroundColor: "transparent",
    animationDuration: 400,
    textStyle: { fontFamily: "Atkinson Hyperlegible", color: p.ink2 },
    grid: { left: 8, right: 16, top: 44, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: p.module,
      borderColor: p.edge,
      textStyle: { color: p.ink, fontFamily: "Atkinson Hyperlegible", fontSize: 13 },
      axisPointer: { type: "line", lineStyle: { color: p.ink3, type: "dashed" } },
    },
    legend: { type: "scroll", top: 0, left: 0, right: 0, icon: "roundRect", pageTextStyle: { color: p.ink3 }, pageIconColor: p.ink2, pageIconInactiveColor: p.edge, itemWidth: 12, itemHeight: 8, textStyle: { color: p.ink2, fontSize: 12 } },
    xAxis: axis,
    yAxis: axis,
    aria: { enabled: true },
  };
}

type Props = {
  option: (p: Palette) => EChartsCoreOption;
  height?: number;
  label: string;
  onClick?: (params: unknown) => void;
  deps?: unknown[];
};

export function Chart({ option, height = 300, label, onClick, deps = [] }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const theme = useResolvedTheme();

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const p = palette();
    const b = base(p) as Record<string, unknown>;
    const o = option(p) as Record<string, unknown>;
    const merge = (k: string) =>
      Array.isArray(o[k]) ? (o[k] as object[]).map((x) => ({ ...(b[k] as object), ...x })) : { ...(b[k] as object), ...(o[k] as object) };
    chart.current?.setOption({ ...b, ...o, xAxis: merge("xAxis"), yAxis: merge("yAxis"), tooltip: merge("tooltip"),
      legend: o.legend === false ? { show: false } : merge("legend"), grid: merge("grid") }, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, ...deps]);

  useEffect(() => {
    if (!chart.current || !onClick) return;
    chart.current.on("click", onClick);
    return () => {
      chart.current?.off("click", onClick);
    };
  }, [onClick]);

  return <div ref={ref} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
