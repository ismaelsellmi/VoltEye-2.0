import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi, type Kpis } from "../lib/api";
import { Chart } from "../components/Chart";
import { ErrorBox, Loading, MachineName, Module, PageTitle, Stat, Status, Table, ToggleTable } from "../components/ui";
import { CAUSES, label } from "../lib/machines";
import { fmtDay, nf, pct } from "../lib/format";

export default function Accueil() {
  const { data: k, error, isLoading } = useApi<Kpis>("/api/kpis");
  const [table, setTable] = useState(false);
  if (error) return <ErrorBox error={error} />;
  if (isLoading || !k) return <Loading height={480} />;

  const rep = [...k.repartition].sort((a, b) => a.kwh - b.kwh);
  const alerts = k.sante.filter((s) => s.alert).length;
  return (
    <>
      <PageTitle kicker={`Atelier de référence · ${k.periode.jours} derniers jours, jusqu'au ${fmtDay(k.periode.fin)}`} title="Vue d'ensemble">
        Sept machines suivies depuis un seul compteur électrique. Chaque chiffre ci-dessous vient de la désagrégation
        du courant général.
      </PageTitle>

      <div className="grid gap-4">
        <Module title="Les 30 derniers jours">
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat value={nf(k.energie_kWh / 1000, 1)} unit="MWh" caption="consommés par l'atelier" />
            <Stat value={nf(k.cout_TND, 0)} unit="TND" caption="coût estimé au tarif de jour" />
            <Stat value={nf(k.co2_kg / 1000, 1)} unit="t CO₂" caption="émissions associées" />
            <Stat value={String(alerts)} caption={alerts ? "machine(s) en alerte de santé" : "aucune machine en alerte de santé"} tone={alerts ? "critical" : "good"} />
          </div>
        </Module>

        <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
          <Module title="Où part l'énergie" aside={<ToggleTable show={table} onChange={setTable} />}>
            {table ? (
              <Table
                caption="Énergie par machine sur 30 jours"
                head={["Machine", "Énergie (kWh)", "Part"]}
                rows={[...rep].reverse().map((r) => [<MachineName m={r.mtype} />, <span className="num">{nf(r.kwh, 0)}</span>, <span className="num">{pct(r.kwh / k.energie_kWh)}</span>])}
              />
            ) : (
              <Chart
                label="Énergie consommée par machine sur 30 jours"
                height={300}
                deps={[k]}
                option={(p) => ({
                  grid: { left: 8, right: 64, top: 8, bottom: 8 },
                  legend: false,
                  tooltip: { trigger: "item", formatter: (x: { name: string; value: number }) => `${x.name}<br/><b>${nf(x.value, 0)} kWh</b> · ${pct(x.value / k.energie_kWh)}` },
                  xAxis: { type: "value", axisLabel: { formatter: (v: number) => nf(v, 0) } },
                  yAxis: { type: "category", data: rep.map((r) => label(r.mtype)), axisLabel: { color: p.ink2, fontFamily: "Atkinson Hyperlegible", fontSize: 13 } },
                  series: [{
                    type: "bar",
                    barWidth: 14,
                    data: rep.map((r) => ({ value: r.kwh, name: label(r.mtype), itemStyle: { color: p.m(r.mtype), borderRadius: [0, 4, 4, 0] } })),
                    label: { show: true, position: "right", color: p.ink2, fontFamily: "IBM Plex Mono", fontSize: 11, formatter: (x: { value: number }) => pct(x.value / k.energie_kWh, 0) },
                  }],
                })}
              />
            )}
          </Module>

          <Module title="Alertes récentes" aside={<Link to="/anomalies" className="text-sm text-accent hover:underline">Toutes les alertes</Link>}>
            <ul className="divide-y divide-edge">
              {k.alertes_recentes.slice(0, 6).map((a) => (
                <li key={`${a.day}-${a.mtype}`} className="flex items-start justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <MachineName m={a.mtype} className="font-bold" />
                    <p className="text-sm text-ink-2">{CAUSES[a.cause] ?? a.cause}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="num text-sm">{fmtDay(a.day)}</p>
                    {a.excess_cost_tnd ? <p className="num text-sm text-ink-3">{nf(a.excess_cost_tnd, 1)} TND</p> : null}
                  </div>
                </li>
              ))}
            </ul>
          </Module>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Module title="Santé des moteurs et équipements" aside={<span className="text-xs text-ink-3">dérive de la distorsion harmonique (THD)</span>}>
            <ul className="space-y-2.5">
              {[...k.sante].sort((a, b) => (a.health ?? 100) - (b.health ?? 100)).map((s) => {
                const level = s.alert ? "critical" : (s.health ?? 100) < 90 ? "warning" : "good";
                return (
                  <li key={s.mtype} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[180px_1fr_110px]">
                    <MachineName m={s.mtype} />
                    <div className="order-3 col-span-2 h-2 overflow-hidden rounded-full bg-module-2 sm:order-none sm:col-span-1">
                      <div className="h-full rounded-full" style={{ width: `${s.health ?? 0}%`, background: `var(--${level === "good" ? "good" : level === "warning" ? "warning" : "critical"})` }} />
                    </div>
                    <span className="text-right">
                      <Status level={level} text={`${nf(s.health, 0)} / 100`} />
                    </span>
                  </li>
                );
              })}
            </ul>
          </Module>

          <Module title="Ce que l'IA a démontré" aside={<Link to="/evaluation" className="text-sm text-accent hover:underline">Méthodes et protocole</Link>}>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
              <div>
                <dt className="text-sm text-ink-2">Machines reconnues par leur signature</dt>
                <dd className="reading text-3xl">{pct(k.modeles.reconnaissance_exactitude)}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-2">Détection des gaspillages, 4 mois jamais vus</dt>
                <dd className="reading text-3xl">F1 {nf(k.modeles.anomalies_f1_test, 2)}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-2">Erreur de la prévision du lendemain</dt>
                <dd className="reading text-3xl">{nf(k.modeles.prevision_mape, 1)} %</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-2">Panne du convoyeur annoncée</dt>
                <dd className="reading text-3xl">{k.modeles.anticipation_panne_jours} jours avant</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-2">Planning optimisé, facture des jours ouvrés</dt>
                <dd className="reading text-3xl">−{nf(k.planning["gain_moyen_%"], 1)} %</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-2">Pointe d'été effacée par VoltEye Grid</dt>
                <dd className="reading text-3xl">−{nf(k.grid.effacement_MW_vs_pratique, 1)} MW</dd>
              </div>
            </dl>
          </Module>
        </div>
      </div>
    </>
  );
}
