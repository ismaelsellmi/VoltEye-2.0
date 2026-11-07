import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, useApi, type ForecastPoint, type Json, type ScheduleDay, type Task } from "../lib/api";
import { Chart } from "../components/Chart";
import { ErrorBox, Loading, Module, PageTitle, Stat, Table } from "../components/ui";
import { fmtDay, fmtShortDay, nf } from "../lib/format";

type Planning = { jours: string[]; jour: ScheduleDay; taches: Task[]; resume: Json };
type Optim = { statut: string; pratique_actuelle: Json; operateur_averti: Json; voltEye: Json };

function profile(base: number[], tasks: Task[], starts: number[]) {
  const p = [...base];
  tasks.forEach((t, k) => {
    for (let h = starts[k]; h < starts[k] + t.duree && h < 24; h++) p[h] += t.kW;
  });
  return p;
}

function peakBands(prices: number[]) {
  const max = Math.max(...prices);
  const bands: [number, number][] = [];
  prices.forEach((v, h) => {
    if (v !== max) return;
    if (bands.length && bands[bands.length - 1][1] === h) bands[bands.length - 1][1] = h + 1;
    else bands.push([h, h + 1]);
  });
  return bands;
}

function ForecastModule() {
  const { data, error, isLoading } = useApi<{ serie: ForecastPoint[]; metriques: Json }>("/api/prevision");
  const serie = data?.serie ?? [];
  const hasBand = serie.some((s) => s.p10 !== null);
  if (error) return <ErrorBox error={error} />;
  if (isLoading || !data) return <Loading height={360} />;
  const models = data.metriques.models as Record<string, Json>;
  return (
    <Module title="Prévision de la consommation du lendemain">
      <Chart
        label="Consommation horaire réelle et prévue la veille, sur la période de test"
        height={340}
        deps={[serie.length]}
        option={(p) => ({
          tooltip: { valueFormatter: (v: number) => (v === null || v === undefined ? "–" : `${nf(v, 1)} kWh`) },
          xAxis: { type: "category", data: serie.map((s) => `${fmtShortDay(s.time)} · ${new Date(s.time).getHours()} h`), axisLabel: { formatter: (v: string) => v.split(" · ")[0] } },
          yAxis: { type: "value", name: "kWh / h", min: 0 },
          dataZoom: [{ type: "inside", startValue: Math.max(0, serie.length - 24 * 10), endValue: serie.length - 1 }, { type: "slider", height: 18, bottom: 0, borderColor: p.edge, textStyle: { color: p.ink3 } }],
          grid: { bottom: 36 },
          series: [
            ...(hasBand
              ? [
                  { name: "P10", type: "line", symbol: "none", stack: "bande", lineStyle: { opacity: 0 }, data: serie.map((s) => s.p10), tooltip: { show: false } },
                  { name: "Fourchette P10–P90", type: "line", symbol: "none", stack: "bande", lineStyle: { opacity: 0 }, areaStyle: { color: p.accent, opacity: 0.15 }, itemStyle: { color: p.accent }, data: serie.map((s) => (s.p90 !== null && s.p10 !== null ? s.p90 - s.p10 : null)) },
                ]
              : []),
            { name: "Réel", type: "line", symbol: "none", lineStyle: { width: 2, color: p.ink }, itemStyle: { color: p.ink }, data: serie.map((s) => s.actual) },
            { name: "Prévision VoltEye", type: "line", symbol: "none", lineStyle: { width: 2, color: p.accent }, itemStyle: { color: p.accent }, data: serie.map((s) => s.p50) },
          ],
          legend: { data: ["Réel", "Prévision VoltEye", ...(hasBand ? ["Fourchette P10–P90"] : [])] },
        })}
      />
      <div className="mt-3">
        <Table
          caption="Erreurs de prévision sur la période de test"
          head={["Méthode", "Erreur moyenne", "Erreur en %"]}
          rows={Object.entries(models).map(([k, v]) => [
            <span className={k.startsWith("VoltEye") ? "font-bold" : ""}>{k.replace("Baseline - ", "Référence : ")}</span>,
            <span className="num">{nf(v.MAE_kWh, 2)} kWh</span>,
            <span className="num">{nf(v["MAPE_%_heures_actives"], 1)} %</span>,
          ])}
        />
      </div>
    </Module>
  );
}

export default function Prevision() {
  const [day, setDay] = useState<string | null>(null);
  const { data, error, isLoading } = useApi<Planning>(day ? `/api/planning?jour=${day}` : "/api/planning");
  const live = useMutation({
    mutationFn: (d: ScheduleDay) => {
      const t0 = performance.now();
      return api<Optim>("/api/optimiser", { method: "POST", body: JSON.stringify({ base_kw: d.base, mois: new Date(d.jour).getMonth() + 1 }) }).then((r) => ({ ...r, ms: performance.now() - t0 }));
    },
  });
  const d = data?.jour;
  const series = useMemo(() => {
    if (!d || !data) return null;
    return {
      actuel: profile(d.base, data.taches, d.ref),
      operateur: d.operateur ? profile(d.base, data.taches, d.operateur) : null,
      voltEye: profile(d.base, data.taches, d.opt),
      bands: peakBands(d.prix),
    };
  }, [d, data]);

  return (
    <>
      <PageTitle kicker="Prévision J+1 et planning des tâches flexibles" title="Prévision et planning">
        La veille, VoltEye prévoit la consommation heure par heure. Un optimiseur place ensuite les tâches qui peuvent
        attendre (cuissons, air comprimé, recharges) aux heures les moins chères, sans dépasser la puissance souscrite.
      </PageTitle>

      <div className="grid gap-4">
        <ForecastModule />

        {error ? <ErrorBox error={error} /> : isLoading || !data || !d || !series ? <Loading height={420} /> : (
          <Module
            title="Planning optimisé d'un jour ouvré"
            aside={
              <label className="flex items-center gap-2 text-sm">
                Jour
                <select className="rounded border border-edge bg-module-2 px-2 py-1" value={d.jour} onChange={(e) => { setDay(e.target.value); live.reset(); }}>
                  {data.jours.map((j) => <option key={j} value={j}>{fmtDay(j)}</option>)}
                </select>
              </label>
            }
          >
            <div className="mb-4 grid grid-cols-2 gap-6 md:grid-cols-4">
              <Stat value={nf(d.facture_ref_TND, 0)} unit="TND" caption={`pratique actuelle · pointe ${nf(d.pointe_ref_kW, 0)} kW`} />
              {d.facture_operateur_TND !== undefined && <Stat value={nf(d.facture_operateur_TND, 0)} unit="TND" caption={`opérateur averti du tarif · pointe ${nf(d.pointe_operateur_kW, 0)} kW`} />}
              <Stat value={nf(d.facture_opt_TND, 0)} unit="TND" caption={`planning VoltEye · pointe ${nf(d.pointe_opt_kW, 0)} kW`} tone="good" />
              <Stat value={`−${nf(100 * (1 - d.facture_opt_TND / d.facture_ref_TND), 1)} %`} caption="sur la facture du jour" tone="good" />
            </div>
            <Chart
              label="Profil de charge horaire du site selon trois plannings, avec les heures de pointe tarifaire"
              height={300}
              deps={[d.jour]}
              option={(p) => ({
                tooltip: { valueFormatter: (v: number) => `${nf(v, 0)} kW` },
                xAxis: { type: "category", data: Array.from({ length: 24 }, (_, h) => `${h} h`), axisLabel: { interval: 2 } },
                yAxis: { type: "value", name: "kW", min: 0 },
                series: [
                  {
                    name: "Pratique actuelle", type: "line", step: "end", symbol: "none", lineStyle: { width: 2, color: p.ink3 }, itemStyle: { color: p.ink3 }, data: series.actuel,
                    markArea: { silent: true, itemStyle: { color: p.signal, opacity: 0.14 }, label: { color: p.ink3, fontSize: 11, fontFamily: "IBM Plex Mono" }, data: series.bands.map(([a, b]) => [{ name: "pointe tarifaire", xAxis: `${a} h` }, { xAxis: `${Math.min(b, 23)} h` }]) },
                  },
                  ...(series.operateur ? [{ name: "Opérateur averti", type: "line", step: "end", symbol: "none", lineStyle: { width: 2, type: "dashed", color: p.ink2 }, itemStyle: { color: p.ink2 }, data: series.operateur }] : []),
                  { name: "Planning VoltEye", type: "line", step: "end", symbol: "none", lineStyle: { width: 3, color: p.accent }, itemStyle: { color: p.accent }, data: series.voltEye },
                ],
              })}
            />
            <div className="mt-3">
              <Table
                caption="Heure de démarrage de chaque tâche flexible"
                head={["Tâche", "Puissance", "Durée", "Actuel", "Opérateur averti", "VoltEye"]}
                rows={data.taches.map((t, k) => [
                  t.nom, <span className="num">{t.kW} kW</span>, <span className="num">{t.duree} h</span>,
                  <span className="num">{d.ref[k]} h</span>, <span className="num">{d.operateur ? `${d.operateur[k]} h` : "–"}</span>,
                  <span className="num font-bold">{d.opt[k]} h</span>,
                ])}
              />
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button onClick={() => live.mutate(d)} disabled={live.isPending} className="rounded-md bg-accent px-4 py-2 font-bold text-accent-ink disabled:opacity-60">
                {live.isPending ? "Optimisation…" : "Relancer l'optimiseur sur ce jour"}
              </button>
              {live.data && (
                <span className="text-sm text-ink-2">
                  Solution {live.data.statut === "1" ? "optimale" : live.data.statut} en <b className="num">{nf(live.data.ms, 0)} ms</b> :
                  facture {nf(live.data.voltEye.facture_TND, 0)} TND, pointe {nf(live.data.voltEye.pointe_kW, 0)} kW.
                </span>
              )}
              {live.error && <ErrorBox error={live.error} />}
            </div>
          </Module>
        )}
      </div>
    </>
  );
}
