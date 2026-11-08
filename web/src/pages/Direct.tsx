import { useNavigate } from "react-router-dom";
import { useLive } from "../lib/live";
import { Chart } from "../components/Chart";
import { Empty, MachineName, Module, PageTitle, Table } from "../components/ui";
import { MACHINES, label } from "../lib/machines";
import { fmtTime, nf, pct } from "../lib/format";

export default function Direct() {
  const { measures, events, state, last } = useLive();
  const navigate = useNavigate();

  if (!measures.length) {
    return (
      <>
        <PageTitle kicker="Compteur général · 1 mesure par seconde" title="Direct" />
        <Empty title="Aucune mesure reçue pour l'instant">
          La passerelle publie une mesure par seconde. Lancez-la avec <code className="num">docker compose up</code>, puis
          revenez sur cette page. État de la liaison : {state}.
        </Empty>
      </>
    );
  }

  const times = measures.map((m) => m.time);
  const est = last?.estime ?? {};
  const running = MACHINES.filter((m) => (est[m] ?? 0) > 0);
  return (
    <>
      <PageTitle kicker="Compteur général · 1 mesure par seconde · 15 dernières minutes" title="Direct">
        La courbe « Mesure totale » est la seule mesure disponible. Les couleurs dessous sont ce que VoltEye en déduit :
        la puissance de chaque machine, reconnue à chaque démarrage ou arrêt.
      </PageTitle>

      <div className="stagger grid gap-4">
        <Module title="Mesure totale et désagrégation par machine">
          <Chart
            label="Puissance mesurée au compteur général et puissance estimée de chaque machine sur les 15 dernières minutes"
            height={360}
            deps={[measures.length, last?.time]}
            option={(p) => ({
              animation: false,
              tooltip: {
                valueFormatter: (v: number) => `${nf(v, 1)} kW`,
              },
              xAxis: { type: "category", data: times, boundaryGap: false, axisLabel: { formatter: (v: string) => fmtTime(v).slice(0, 5), interval: Math.max(1, Math.floor(times.length / 6)) } },
              yAxis: { type: "value", name: "kW", min: 0 },
              series: [
                ...MACHINES.map((m) => ({
                  name: label(m),
                  type: "line",
                  stack: "machines",
                  step: "end",
                  symbol: "none",
                  lineStyle: { width: 0 },
                  areaStyle: { color: p.m(m), opacity: 0.8 },
                  itemStyle: { color: p.m(m) },
                  data: measures.map((r) => r.estime?.[m] ?? 0),
                })),
                { name: "Mesure totale", type: "line", symbol: "none", lineStyle: { color: p.ink, width: 2 }, itemStyle: { color: p.ink }, data: measures.map((r) => r.p_kw) },
              ],
            })}
          />
        </Module>

        <div className="grid gap-4 2xl:grid-cols-[2fr_3fr]">
          <Module title={`Machines en marche : ${running.length} sur ${MACHINES.length}`}>
            <Table
              caption="État estimé de chaque machine"
              head={["Machine", "État", "Estimé", "Mesuré"]}
              rows={MACHINES.map((m) => {
                const on = (est[m] ?? 0) > 0;
                return [
                  <MachineName m={m} />,
                  <span className={`inline-flex items-center gap-1.5 ${on ? "font-bold" : "text-ink-3"}`}><span aria-hidden className={`h-1.5 w-1.5 rounded-full ${on ? "live-dot bg-signal" : "bg-ink-3/50"}`} />{on ? "En marche" : "À l'arrêt"}</span>,
                  <span className="num">{nf(est[m] ?? 0, 1)} kW</span>,
                  <span className="num text-ink-3">{last?.verite ? `${nf(last.verite[m] ?? 0, 1)} kW` : "–"}</span>,
                ];
              })}
            />
            <p className="mt-2 text-xs text-ink-3">« Mesuré » : sous-compteurs du simulateur, affichés pour vérifier l'estimation.</p>
          </Module>

          <Module title="Journal des événements reconnus">
            {events.length ? (
              <Table
                caption="Derniers démarrages et arrêts reconnus"
                head={["Heure", "Événement", "ΔP", "Machine reconnue", "Confiance", ""]}
                rows={events.slice(0, 12).map((e) => [
                  <span className="num">{fmtTime(e.time)}</span>,
                  e.direction === "marche" ? "Démarrage" : "Arrêt",
                  <span className="num">{e.delta_kw > 0 ? "+" : ""}{nf(e.delta_kw, 1)} kW</span>,
                  <span className="inline-flex items-center gap-2">
                    <MachineName m={e.mtype} />
                    {e.verite && e.verite !== e.mtype && <span className="text-xs text-critical">(réel : {label(e.verite)})</span>}
                  </span>,
                  <span className="num">{e.confiance !== null ? pct(e.confiance, 0) : "–"}</span>,
                  e.waveform ? (
                    <button className="link text-sm" onClick={() => navigate(`/reconnaissance?t=${encodeURIComponent(e.time)}`)}>
                      Signature
                    </button>
                  ) : null,
                ])}
              />
            ) : (
              <Empty title="Pas encore d'événement">Le prochain démarrage ou arrêt de machine apparaîtra ici.</Empty>
            )}
          </Module>
        </div>
      </div>
    </>
  );
}
