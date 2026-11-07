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

type Shap = { importance_moyenne_kWh: Record<string, number>; heure?: { time: string; base: number; contributions: [string, number][] } };

function ShapModule({ hour }: { hour: string | null }) {
  const { data } = useApi<Shap>(hour ? `/api/prevision/explication?heure=${encodeURIComponent(hour)}` : "/api/prevision/explication");
  if (!data) return null;
  const imp = Object.entries(data.importance_moyenne_kWh).slice(0, 6).reverse();
  const h = data.heure;
  return (
    <Module title="Pourquoi le modèle prévoit cela (SHAP)">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-1 text-sm text-ink-2">Poids moyen de chaque information dans la prévision (kWh)</p>
          <Chart
            label="Importance moyenne des variables de la prévision selon SHAP"
            height={220}
            deps={[data]}
            option={(p) => ({
              legend: false,
              grid: { left: 8, right: 48, top: 4, bottom: 4 },
              tooltip: { trigger: "item", formatter: (x: { name: string; value: number }) => `${x.name} : <b>${nf(x.value, 2)} kWh</b>` },
              xAxis: { type: "value", show: false },
              yAxis: { type: "category", data: imp.map(([k]) => k), axisLabel: { color: p.ink2, fontSize: 12 } },
              series: [{ type: "bar", barWidth: 12, data: imp.map(([k, v]) => ({ value: v, name: k, itemStyle: { color: p.accent, borderRadius: [0, 4, 4, 0] } })),
                label: { show: true, position: "right", color: p.ink2, fontFamily: "IBM Plex Mono", fontSize: 11, formatter: (x: { value: number }) => nf(x.value, 2) } }],
            })}
          />
        </div>
        <div>
          {h ? (
            <>
              <p className="mb-2 text-sm text-ink-2">
                {fmtShortDay(h.time)} à {new Date(h.time.replace(" ", "T")).getHours()} h : partant d'une moyenne de <b className="num">{nf(h.base, 1)} kWh</b>, chaque information pousse la prévision :
              </p>
              <ul className="space-y-1.5">
                {h.contributions.map(([k, v]) => (
                  <li key={k} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
                    <span>{k}</span>
                    <span className={`num font-bold ${v >= 0 ? "text-accent" : "text-ink-3"}`}>{v >= 0 ? "+" : "−"}{nf(Math.abs(v), 2)} kWh</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-ink-2">Cliquez sur une heure du graphique de prévision pour voir ce qui explique cette valeur.</p>
          )}
        </div>
      </div>
    </Module>
  );
}

function ForecastModule({ onPick }: { onPick: (t: string) => void }) {
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
        onClick={(x) => onPick(serie[(x as { dataIndex: number }).dataIndex].time)}
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
      {data.metriques.quantiles && (
        <p className="mt-2 text-sm text-ink-2">
          Fourchette P10–P90 calibrée : <b className="num">{nf(100 * data.metriques.quantiles.couverture_P10_P90, 1)} %</b> des heures réelles y
          tombent (cible 80 %), largeur moyenne {nf(data.metriques.quantiles.largeur_moyenne_kWh, 1)} kWh.
        </p>
      )}
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

type Solar = {
  installation: { kWc: number };
  production_MWh_an: number; productible_kWh_kWc: number; "autoconsommation_%": number; "autoproduction_%": number;
  economie_TND_an: number; co2_evite_t_an: number;
  pointe_tarifaire_ete: { achat_moyen_sans_pv_kW: number; achat_moyen_avec_pv_kW: number };
  "prevision_J+1": Record<string, Json>;
  semaine_ete: { time: string[]; charge_kW: number[]; pv_kW: number[]; achat_reseau_kW: number[] };
};

function SolarModule() {
  const { data: s } = useApi<Solar>("/api/solaire");
  if (!s) return null;
  const w = s.semaine_ete;
  return (
    <Module title={`Solaire en toiture · ${s.installation.kWc} kWc`}>
      <div className="mb-4 grid grid-cols-2 gap-6 md:grid-cols-4">
        <Stat value={nf(s.production_MWh_an, 0)} unit="MWh/an" caption={`${nf(s.productible_kWh_kWc, 0)} kWh par kWc installé`} />
        <Stat value={`${nf(s["autoconsommation_%"], 0)} %`} caption={`autoconsommés ; ${nf(s["autoproduction_%"], 0)} % des besoins couverts`} />
        <Stat value={nf(s.economie_TND_an, 0)} unit="TND/an" caption={`et ${nf(s.co2_evite_t_an, 1)} t de CO₂ évitées`} tone="good" />
        <Stat value={`${nf(s.pointe_tarifaire_ete.achat_moyen_sans_pv_kW, 0)} → ${nf(s.pointe_tarifaire_ete.achat_moyen_avec_pv_kW, 0)}`} unit="kW" caption="achat moyen au réseau pendant la pointe tarifaire d'été" tone="good" />
      </div>
      <Chart
        label="Semaine d'été : consommation du site, production solaire et achat au réseau"
        height={280}
        deps={[w.time.length]}
        option={(p) => ({
          tooltip: { valueFormatter: (v: number) => `${nf(v, 1)} kW` },
          xAxis: { type: "category", data: w.time.map((t) => `${fmtShortDay(t)} · ${new Date(t).getHours()} h`), axisLabel: { formatter: (v: string) => v.split(" · ")[0], interval: 23 } },
          yAxis: { type: "value", name: "kW", min: 0 },
          series: [
            { name: "Production solaire", type: "line", symbol: "none", lineStyle: { width: 0 }, areaStyle: { color: p.signal, opacity: 0.45 }, itemStyle: { color: p.signal }, data: w.pv_kW },
            { name: "Consommation du site", type: "line", symbol: "none", lineStyle: { width: 1.5, color: p.ink3 }, itemStyle: { color: p.ink3 }, data: w.charge_kW },
            { name: "Achat au réseau", type: "line", symbol: "none", lineStyle: { width: 2, color: p.accent }, itemStyle: { color: p.accent }, data: w.achat_reseau_kW },
          ],
        })}
      />
      <p className="mt-2 text-xs text-ink-3">
        Modèle physique (position du soleil, ciel clair, clarté mensuelle de Tunis), panneaux plein sud inclinés à 30°. Le solaire
        produit pendant la pointe tarifaire d'été : c'est là qu'il allège le plus le réseau.
      </p>
    </Module>
  );
}

export default function Prevision() {
  const [day, setDay] = useState<string | null>(null);
  const [hour, setHour] = useState<string | null>(null);
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
        <ForecastModule onPick={setHour} />
        <ShapModule hour={hour} />
        <SolarModule />

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
