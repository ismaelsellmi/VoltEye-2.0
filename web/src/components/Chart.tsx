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
import { useResolvedTheme } from "../lib/theme";
import { base, palette, type Palette } from "../lib/chartTheme";

echarts.use([
  BarChart, LineChart, CustomChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent,
  MarkAreaComponent, MarkPointComponent, DataZoomComponent, VisualMapComponent, AriaComponent, CanvasRenderer,
]);

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
