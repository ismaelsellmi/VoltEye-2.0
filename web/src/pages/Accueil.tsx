import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Coins, HeartPulse, Leaf, Zap } from "lucide-react";
import { useApi, type Kpis } from "../lib/api";
import { Chart } from "../components/Chart";
import { ErrorBox, Loading, MachineName, Module, PageTitle, Stat, Status, Table, ToggleTable } from "../components/ui";
import { CAUSES, label } from "../lib/machines";
import { fmtDay, nf, pct } from "../lib/format";

const LEVEL_VAR = { good: "--good", warning: "--warning", critical: "--critical" } as const;

export default function Accueil() {
  const { data: k, error, isLoading } = useApi<Kpis>("/api/kpis");
  const [table, setTable] = useState(false);
  if (error) return <ErrorBox error={error} />;
  if (isLoading || !k) return <Loading height={480} />;

  const rep = [...k.repartition].sort((a, b) => a.kwh - b.kwh);
  const alerts = k.sante.filter((s) => s.alert).length;
  const proofs: [string, string][] = [
    ["Machines reconnues par leur signature", pct(k.modeles.reconnaissance_exactitude)],
    ["Détection des gaspillages, 4 mois jamais vus", `F1 ${nf(k.modeles.anomalies_f1_test, 2)}`],
    ["Erreur de la prévision du lendemain", `${nf(k.modeles.prevision_mape, 1)} %`],
    ["Panne du convoyeur annoncée", `${k.modeles.anticipation_panne_jours} jours avant`],
    ["Planning optimisé, facture des jours ouvrés", `−${nf(k.planning["gain_moyen_%"], 1)} %`],
    ["Pointe d'été effacée par VoltEye Grid", `−${nf(k.grid.effacement_MW_vs_pratique, 1)} MW`],
  ];
  return (
    <>
      <PageTitle kicker={`Atelier de référence · ${k.periode.jours} derniers jours, jusqu'au ${fmtDay(k.periode.fin)}`} title="Vue d'ensemble">
        Sept machines suivies depuis un seul compteur électrique. Chaque chiffre ci-dessous vient de la désagrégation
        du courant général.
      </PageTitle>

      <div className="stagger grid gap-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat icon={Zap} value={nf(k.energie_kWh / 1000, 1)} unit="MWh" caption="consommés par l'atelier" />
          <Stat icon={Coins} value={nf(k.cout_TND, 0)} unit="TND" caption="coût estimé au tarif de jour" />
          <Stat icon={Leaf} value={nf(k.co2_kg / 1000, 1)} unit="t CO₂" caption="émissions associées" />
          <Stat icon={HeartPulse} value={String(alerts)} caption={alerts ? "machine(s) en alerte de santé" : "aucune machine en alerte de santé"} tone={alerts ? "critical" : "good"} />
        </div>

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
                  yAxis: { type: "category", data: rep.map((r) => label(r.mtype)), axisLabel: { color: p.ink2, fontFamily: "Manrope Variable", fontSize: 13, fontWeight: 600 } },
                  series: [{
                    type: "bar",
                    barWidth: 14,
                    showBackground: true,
                    backgroundStyle: { color: p.grid, borderRadius: 7 },
                    data: rep.map((r) => ({ value: r.kwh, name: label(r.mtype), itemStyle: { color: p.m(r.mtype), borderRadius: 7 } })),
                    label: { show: true, position: "right", color: p.ink2, fontFamily: "IBM Plex Mono", fontSize: 11, formatter: (x: { value: number }) => pct(x.value / k.energie_kWh, 0) },
                  }],
                })}
              />
            )}
          </Module>

          <Module
            title="Alertes récentes"
            aside={
              <Link to="/anomalies" className="link inline-flex items-center gap-1 text-sm">
                Toutes les alertes <ArrowUpRight size={14} aria-hidden />
              </Link>
            }
          >
            <ul className="-mx-2 space-y-1">
              {k.alertes_recentes.slice(0, 6).map((a) => (
                <li key={`${a.day}-${a.mtype}`}>
                  <Link to="/anomalies" className="flex items-start justify-between gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-module-2">
                    <div className="min-w-0">
                      <MachineName m={a.mtype} className="font-bold" />
                      <p className="mt-0.5 pl-[18px] text-sm text-ink-2">{CAUSES[a.cause] ?? a.cause}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="num text-sm">{fmtDay(a.day)}</p>
                      {a.excess_cost_tnd ? <p className="num text-sm font-semibold text-critical">{nf(a.excess_cost_tnd, 1)} TND</p> : null}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Module>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Module title="Santé des moteurs et équipements" aside={<span className="text-xs text-ink-3">dérive de la distorsion harmonique (THD)</span>}>
            <ul className="space-y-3">
              {[...k.sante].sort((a, b) => (a.health ?? 100) - (b.health ?? 100)).map((s, i) => {
                const level = s.alert ? "critical" : (s.health ?? 100) < 90 ? "warning" : "good";
                return (
                  <li key={s.mtype} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[170px_1fr_118px]">
                    <MachineName m={s.mtype} className="font-semibold" />
                    <div className="order-3 col-span-2 h-2 overflow-hidden rounded-full bg-module-2 sm:order-none sm:col-span-1">
                      <div
                        className="bar-grow h-full rounded-full"
                        style={{
                          width: `${s.health ?? 0}%`,
                          animationDelay: `${150 + i * 60}ms`,
                          background: `linear-gradient(90deg, color-mix(in srgb, var(${LEVEL_VAR[level]}) 55%, transparent), var(${LEVEL_VAR[level]}))`,
                        }}
                      />
                    </div>
                    <span className="text-right">
                      <Status level={level} text={`${nf(s.health, 0)} / 100`} />
                    </span>
                  </li>
                );
              })}
            </ul>
          </Module>

          <Module
            title="Ce que l'IA a démontré"
            aside={
              <Link to="/evaluation" className="link inline-flex items-center gap-1 text-sm">
                Méthodes et protocole <ArrowUpRight size={14} aria-hidden />
              </Link>
            }
          >
            <dl className="grid grid-cols-2 gap-3">
              {proofs.map(([t, v]) => (
                <div key={t} className="rounded-2xl border border-edge bg-module-2 p-3.5">
                  <dt className="text-[13px] leading-snug text-ink-2">{t}</dt>
                  <dd className="reading mt-1.5 text-[30px]">{v}</dd>
                </div>
              ))}
            </dl>
          </Module>
        </div>
      </div>
    </>
  );
}
