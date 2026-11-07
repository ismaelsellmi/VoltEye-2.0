import { useState } from "react";
import { useApi, type AnomalyDay, type HealthDay, type Json } from "../lib/api";
import { Chart } from "../components/Chart";
import { Empty, ErrorBox, Loading, MachineDot, Module, PageTitle, Segmented, Status, Table } from "../components/ui";
import { CAUSES, LABELS, MACHINES, TECH } from "../lib/machines";
import { fmtDay, nf } from "../lib/format";

export default function Anomalies() {
  const [m, setM] = useState<string>("compresseur");
  const an = useApi<AnomalyDay[]>(`/api/anomalies?machine=${m}`);
  const he = useApi<HealthDay[]>(`/api/sante?machine=${m}`);
  const ev = useApi<Json>("/api/evaluation");
  const proto = ev.data?.anomalies?.protocole;

  const days = an.data ?? [];
  const alerts = days.filter((d) => d.alert).reverse();
  const cost = alerts.reduce((s, d) => s + (d.excess_cost_tnd ?? 0), 0);
  const lastHealth = he.data?.[he.data.length - 1];

  return (
    <>
      <PageTitle kicker="Gaspillages détectés et santé des machines" title="Anomalies et santé">
        Pour chaque machine, un modèle apprend la consommation normale (heure, jour, production, température). Un écart
        anormal déclenche une alerte avec sa cause, son coût et l'action à mener.
      </PageTitle>

      <div className="mb-4">
        <Segmented
          ariaLabel="Machine"
          value={m}
          onChange={setM}
          options={MACHINES.map((k) => ({ value: k, label: <span className="inline-flex items-center gap-1.5"><MachineDot m={k} />{LABELS[k]}</span> }))}
        />
      </div>

      <div className="grid gap-4">
        <Module
          title={`${LABELS[m]} · énergie journalière réelle et attendue`}
          aside={<span className="text-sm text-ink-2"><b className="num">{alerts.length}</b> alertes · <b className="num">{nf(cost, 0)}</b> TND d'excès</span>}
        >
          {an.error ? <ErrorBox error={an.error} /> : an.isLoading ? <Loading height={320} /> : (
            <Chart
              label={`Énergie journalière réelle et attendue de la machine ${LABELS[m]}, avec les jours en alerte`}
              height={320}
              deps={[m, days.length]}
              option={(p) => ({
                tooltip: { valueFormatter: (v: number) => (v === null || v === undefined ? "–" : `${nf(v, 1)} kWh`) },
                xAxis: { type: "category", data: days.map((d) => d.day), axisLabel: { formatter: (v: string) => fmtDay(v).replace(/ \d{4}$/, "") } },
                yAxis: { type: "value", name: "kWh / jour" },
                dataZoom: [{ type: "inside" }],
                series: [
                  {
                    name: "Réelle", type: "line", symbol: "none", lineStyle: { width: 2, color: p.m(m) }, itemStyle: { color: p.m(m) },
                    data: days.map((d) => d.energy_kwh),
                    markArea: proto ? {
                      silent: true,
                      itemStyle: { color: p.grid, opacity: 0.6 },
                      label: { color: p.ink3, fontFamily: "IBM Plex Mono", fontSize: 11, position: "insideTop" },
                      data: [[{ name: "rodage", xAxis: days[0]?.day }, { xAxis: proto.validation[0] }], [{ name: "test (jamais vu)", xAxis: proto.test[0] }, { xAxis: days[days.length - 1]?.day }]],
                    } : undefined,
                  },
                  { name: "Attendue (modèle)", type: "line", symbol: "none", lineStyle: { width: 2, type: "dashed", color: p.ink3 }, itemStyle: { color: p.ink3 }, data: days.map((d) => d.expected_kwh) },
                  {
                    name: "Alerte", type: "line", lineStyle: { opacity: 0 }, symbol: "diamond", symbolSize: 10,
                    itemStyle: { color: p.critical, borderColor: p.module, borderWidth: 2 },
                    data: days.map((d) => (d.alert ? d.energy_kwh : null)),
                  },
                ],
              })}
            />
          )}
          {proto && (
            <p className="mt-2 text-xs text-ink-3">
              Modèle réentraîné chaque mois sur le passé uniquement ; seuil réglé sur la validation ({fmtDay(proto.validation[0])} – {fmtDay(proto.validation[1])}),
              score publié sur le test ({fmtDay(proto.test[0])} – {fmtDay(proto.test[1])}).
            </p>
          )}
        </Module>

        <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
          <Module title="Alertes et actions recommandées">
            {alerts.length ? (
              <Table
                caption={`Alertes de la machine ${LABELS[m]}`}
                head={["Jour", "Cause", "Score", "Excès", "Action"]}
                rows={alerts.slice(0, 12).map((d) => [
                  <span className="num whitespace-nowrap">{fmtDay(d.day)}</span>,
                  CAUSES[d.cause ?? ""] ?? d.cause,
                  <span className="num">{nf(d.score, 1)}</span>,
                  <span className="num whitespace-nowrap">{nf(d.excess_cost_tnd, 1)} TND</span>,
                  <span className="text-ink-2">{d.recommandation}</span>,
                ])}
              />
            ) : (
              <Empty title="Aucune alerte pour cette machine">Sa consommation est restée dans la plage attendue toute l'année.</Empty>
            )}
          </Module>

          <Module title={`Santé · ${TECH[m]}`}>
            {he.data && lastHealth ? (
              <>
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="reading text-4xl">{nf(lastHealth.health, 0)}<span className="ml-1 font-sans text-sm font-normal text-ink-3">/ 100</span></span>
                  <Status level={lastHealth.alert ? "critical" : (lastHealth.health ?? 100) < 90 ? "warning" : "good"} />
                </div>
                <Chart
                  label={`Dérive de la distorsion harmonique de la machine ${LABELS[m]} par rapport à sa référence`}
                  height={200}
                  deps={[m, he.data.length]}
                  option={(p) => ({
                    legend: false,
                    grid: { top: 20 },
                    tooltip: { valueFormatter: (v: number) => (v === null || v === undefined ? "–" : `${nf(v * 100, 1)} %`) },
                    xAxis: { type: "category", data: he.data!.map((d) => d.day), axisLabel: { formatter: (v: string) => fmtDay(v).replace(/ \d{4}$/, "") } },
                    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${nf(v * 100, 0)} %` } },
                    series: [{
                      name: "Dérive du THD", type: "line", symbol: "none", lineStyle: { width: 2, color: p.m(m) }, itemStyle: { color: p.m(m) },
                      data: he.data!.map((d) => d.drift),
                      markLine: { symbol: "none", lineStyle: { color: p.critical, type: "dashed" }, label: { formatter: "seuil d'alerte +25 %", color: p.critical, fontSize: 11 }, data: [{ yAxis: 0.25 }] },
                    }],
                  })}
                />
                <p className="mt-1 text-xs text-ink-3">Un moteur qui s'use déforme davantage le courant : sa distorsion harmonique monte.</p>
              </>
            ) : he.error ? <ErrorBox error={he.error} /> : <Loading height={240} />}
          </Module>
        </div>
      </div>
    </>
  );
}
