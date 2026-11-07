import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, useApi, type Json } from "../lib/api";
import { useLive, type LiveEvent } from "../lib/live";
import { Chart } from "../components/Chart";
import { Empty, ErrorBox, Loading, MachineName, Module, PageTitle, Table } from "../components/ui";
import { LABELS, MACHINES, label } from "../lib/machines";
import { fmtTime, nf, pct } from "../lib/format";

type Gaf = { sequences: Record<string, number[]>; image: number[][][]; harmoniques: number[] };

/** Image GAF couleur (canaux R, V, B = approximation, détail, harmoniques), agrandie sans lissage. */
function GafCanvas({ image, overlay, size = 224, title }: { image: number[][][]; overlay?: number[][]; size?: number; title: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const n = image[0].length;
    const ctx = c.getContext("2d")!;
    const img = ctx.createImageData(n, n);
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        const k = 4 * (i * n + j);
        for (let ch = 0; ch < 3; ch++) img.data[k + ch] = image.length === 1 ? (image[0][i][j] + 1) * 127.5 : (image[ch][i][j] + 1) * 127.5;
        if (image.length === 1) img.data[k + 1] = img.data[k + 2] = img.data[k];
        img.data[k + 3] = 255;
      }
    c.width = n;
    c.height = n;
    ctx.putImageData(img, 0, 0);
    if (overlay) {
      for (let i = 0; i < n; i++)
        for (let j = 0; j < n; j++) {
          const a = overlay[i][j];
          if (a > 0.35) {
            ctx.fillStyle = `rgba(242, 194, 0, ${Math.min(0.75, a * 0.75)})`;
            ctx.fillRect(j, i, 1, 1);
          }
        }
    }
  }, [image, overlay]);
  return <canvas ref={ref} title={title} aria-label={title} role="img" style={{ width: size, height: size, imageRendering: "pixelated" }} className="rounded border border-edge" />;
}

export default function Reconnaissance() {
  const { events } = useLive();
  const [params, setParams] = useSearchParams();
  const [showCam, setShowCam] = useState(true);
  const withWave = events.filter((e) => e.waveform && e.waveform.length === 128);
  const chosen: LiveEvent | undefined = withWave.find((e) => e.time === params.get("t")) ?? withWave[0];
  const gaf = useQuery({
    queryKey: ["gaf", chosen?.time],
    queryFn: () => api<Gaf>("/api/gaf", { method: "POST", body: JSON.stringify({ waveform: chosen!.waveform }) }),
    enabled: !!chosen,
    staleTime: Infinity,
  });
  const evalq = useApi<Json>("/api/evaluation");
  const proba = useMemo(
    () => (chosen ? MACHINES.map((m) => ({ m, p: chosen.proba[m] ?? 0 })).sort((a, b) => a.p - b.p) : []),
    [chosen],
  );

  return (
    <>
      <PageTitle kicker="Étape de reconnaissance · un événement à la fois" title="Reconnaissance">
        À chaque démarrage, VoltEye isole la variation du courant (40 ms), la décompose, la transforme en image et
        laisse un réseau de neurones décider quelle machine vient de changer d'état.
      </PageTitle>

      {!chosen ? (
        <Empty title="Aucun événement à analyser">Les événements reconnus par la passerelle arrivent ici dès qu'une machine démarre ou s'arrête.</Empty>
      ) : (
        <div className="grid gap-4">
          <Module title="Événement analysé">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <label className="flex items-center gap-2 text-sm">
                Événement
                <select
                  className="rounded border border-edge bg-module-2 px-2 py-1"
                  value={chosen.time}
                  onChange={(e) => setParams({ t: e.target.value })}
                >
                  {withWave.slice(0, 30).map((e) => (
                    <option key={e.time} value={e.time}>
                      {fmtTime(e.time)} · {e.direction === "marche" ? "démarrage" : "arrêt"} · {label(e.mtype)}
                    </option>
                  ))}
                </select>
              </label>
              <span className="num text-sm text-ink-2">ΔP {nf(chosen.delta_kw, 2)} kW</span>
              <span className="text-sm">
                Décision : <MachineName m={chosen.mtype} className="font-bold" /> · confiance <span className="num">{pct(chosen.confiance ?? 0, 1)}</span>
              </span>
            </div>
          </Module>

          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
            <Module title="1 · Forme d'onde isolée (après − avant)">
              <Chart
                label="Forme d'onde du courant de l'événement sur 40 millisecondes"
                height={220}
                deps={[chosen.time]}
                option={(p) => ({
                  legend: false,
                  grid: { top: 16 },
                  xAxis: { type: "category", data: chosen.waveform!.map((_, i) => nf((i / 3200) * 1000, 1)), name: "ms", axisLabel: { interval: 31 } },
                  yAxis: { type: "value", name: "A" },
                  tooltip: { valueFormatter: (v: number) => `${nf(v, 2)} A` },
                  series: [{ type: "line", symbol: "none", data: chosen.waveform, lineStyle: { width: 2, color: p.m(chosen.mtype ?? "four") }, itemStyle: { color: p.m(chosen.mtype ?? "four") } }],
                })}
              />
            </Module>
            <Module title="2 · Trois séquences">
              {gaf.isLoading ? <Loading height={220} /> : gaf.error ? <ErrorBox error={gaf.error} /> : (
                <Chart
                  label="Approximation et détail de l'ondelette db4, et contenu harmonique, rééchantillonnés sur 32 points"
                  height={220}
                  deps={[gaf.data]}
                  option={(p) => ({
                    tooltip: { valueFormatter: (v: number) => nf(v, 3) },
                    xAxis: { type: "category", data: Array.from({ length: 32 }, (_, i) => i + 1), axisLabel: { show: false } },
                    yAxis: { type: "value", axisLabel: { show: false }, splitLine: { show: false } },
                    series: [
                      ["approximation", "Approximation (R)", "#d63d2e"],
                      ["detail", "Détail (V)", "#1f8a3b"],
                      ["harmoniques", "Harmoniques (B)", p.accent],
                    ].map(([k, n, c]) => {
                      const s = gaf.data!.sequences[k];
                      const lo = Math.min(...s), hi = Math.max(...s);
                      return { name: n, type: "line", symbol: "none", lineStyle: { width: 2, color: c }, itemStyle: { color: c }, data: s.map((v) => (hi - lo < 1e-9 ? 0 : (2 * (v - lo)) / (hi - lo) - 1)) };
                    }),
                  })}
                />
              )}
            </Module>
            <Module title="3 · Image GAF 32 × 32">
              {gaf.data ? (
                <div className="flex flex-col items-center gap-3">
                  <GafCanvas image={gaf.data.image} overlay={showCam ? chosen.gradcam ?? undefined : undefined} title="Image GAF couleur fusionnée" />
                  {chosen.gradcam && (
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={showCam} onChange={(e) => setShowCam(e.target.checked)} />
                      Zones qui ont décidé (Grad-CAM)
                    </label>
                  )}
                  <div className="flex gap-2">
                    {["Approximation", "Détail", "Harmoniques"].map((t, i) => (
                      <figure key={t} className="text-center">
                        <GafCanvas image={[gaf.data!.image[i]]} size={64} title={`Canal ${t}`} />
                        <figcaption className="mt-1 text-[11px] text-ink-3">{t}</figcaption>
                      </figure>
                    ))}
                  </div>
                </div>
              ) : (
                <Loading height={220} />
              )}
            </Module>
            <Module title="4 · Décision du réseau">
              <Chart
                label="Probabilité attribuée à chaque type de machine"
                height={220}
                deps={[chosen.time]}
                option={(p) => ({
                  legend: false,
                  grid: { left: 8, right: 48, top: 4, bottom: 4 },
                  tooltip: { trigger: "item", formatter: (x: { name: string; value: number }) => `${x.name} : <b>${pct(x.value)}</b>` },
                  xAxis: { type: "value", max: 1, show: false },
                  yAxis: { type: "category", data: proba.map((x) => LABELS[x.m]), axisLabel: { color: p.ink2, fontSize: 12 } },
                  series: [{
                    type: "bar", barWidth: 12,
                    data: proba.map((x) => ({ value: x.p, name: LABELS[x.m], itemStyle: { color: p.m(x.m), borderRadius: [0, 4, 4, 0] } })),
                    label: { show: true, position: "right", color: p.ink2, fontFamily: "IBM Plex Mono", fontSize: 11, formatter: (x: { value: number }) => (x.value >= 0.01 ? pct(x.value, 0) : "") },
                  }],
                })}
              />
            </Module>
          </div>

          <Module title="Comment la reconnaissance a été évaluée">
            {evalq.data ? (
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <p className="mb-2 text-sm text-ink-2">
                    Formes d'onde simulées de 7 types de machines : {nf(evalq.data.reconnaissance.n_train, 0)} événements
                    d'apprentissage, {nf(evalq.data.reconnaissance.n_test, 0)} de test.
                  </p>
                  <Table
                    caption="Exactitude des quatre approches comparées"
                    head={["Approche", "Exactitude", "Bruit × 3"]}
                    rows={Object.entries(evalq.data.reconnaissance.models as Record<string, Json>).map(([k, v]) => [
                      <span className={k.startsWith("D") ? "font-bold" : ""}>{k}</span>,
                      <span className="num">{pct(v.accuracy)}</span>,
                      <span className="num">{pct(v.accuracy_bruit_x3)}</span>,
                    ])}
                  />
                </div>
                {evalq.data.hipe && (
                  <div>
                    <p className="mb-2 text-sm text-ink-2">Mesures réelles (usine HIPE du KIT) : signatures de 7 machines, découpage chronologique.</p>
                    <Table
                      caption="Reconnaissance sur signatures réelles"
                      head={["Approche", "Exactitude", "F1 macro"]}
                      rows={Object.entries(evalq.data.hipe.signatures as Record<string, Json>)
                        .filter(([k]) => k !== "machines")
                        .map(([k, v]) => [<span className={k.startsWith("VoltEye") ? "font-bold" : ""}>{k}</span>, <span className="num">{pct(v.exactitude)}</span>, <span className="num">{nf(v.f1_macro, 3)}</span>])}
                    />
                  </div>
                )}
              </div>
            ) : (
              <Loading height={120} />
            )}
          </Module>
        </div>
      )}
    </>
  );
}
