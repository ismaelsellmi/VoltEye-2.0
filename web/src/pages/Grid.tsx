import { useMemo, useState } from "react";
import { useApi, type GridDay, type GridSummary, type Zone } from "../lib/api";
import { Chart } from "../components/Chart";
import { ErrorBox, Loading, Module, PageTitle, Stat, Table, ToggleTable } from "../components/ui";
import { fmtDay, nf } from "../lib/format";
import tunisia from "../data/tunisia.json";

type GridIndex = { resume: GridSummary; zones: Zone[]; jours: string[] };

// Projection équirectangulaire corrigée de la latitude, suffisante à l'échelle de la Tunisie
const BOX = { lon0: 7.4, lon1: 11.7, lat0: 30.1, lat1: 37.6 };
const K = Math.cos((34 * Math.PI) / 180);
const W = 300;
const H = Math.round((W * (BOX.lat1 - BOX.lat0)) / ((BOX.lon1 - BOX.lon0) * K));
const px = (lon: number) => ((lon - BOX.lon0) / (BOX.lon1 - BOX.lon0)) * W;
const py = (lat: number) => ((BOX.lat1 - lat) / (BOX.lat1 - BOX.lat0)) * H;

function outline() {
  const polys = (tunisia as { coordinates: number[][][][] }).coordinates;
  return polys.map((poly) => "M" + poly[0].map(([lon, lat]) => `${px(lon).toFixed(1)},${py(lat).toFixed(1)}`).join("L") + "Z").join("");
}

function ZoneMap({ zones, active, onPick }: { zones: Zone[]; active: string | null; onPick: (s: string) => void }) {
  const d = useMemo(outline, []);
  const max = Math.max(...zones.map((z) => z.flexibilite_MW));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto block h-auto w-full max-w-[340px]" role="img" aria-label="Carte de la Tunisie et des 10 zones industrielles ; la taille des cercles est proportionnelle à la flexibilité de chaque zone">
      <path d={d} fill="var(--module-2)" stroke="var(--edge)" strokeWidth={1} />
      {zones.map((z) => {
        const r = 4 + 12 * Math.sqrt(z.flexibilite_MW / max);
        const on = active === z.site;
        return (
          <g key={z.site} onClick={() => onPick(z.site)} className="cursor-pointer" tabIndex={0} role="button" aria-label={`${z.site} : ${nf(z.flexibilite_MW, 1)} MW de flexibilité`}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onPick(z.site)}>
            <circle cx={px(z.lon)} cy={py(z.lat)} r={r} fill="var(--accent)" fillOpacity={on ? 0.9 : 0.45} stroke="var(--module)" strokeWidth={2} />
            {on && (
              <text x={px(z.lon) + r + 4} y={py(z.lat) + 4} fontSize={11} fill="var(--ink)" fontFamily="Atkinson Hyperlegible" fontWeight={700}>
                {z.site.replace("ZI ", "")}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function Grid() {
  const idx = useApi<GridIndex>("/api/grid");
  const [day, setDay] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [table, setTable] = useState(false);
  const current = day ?? idx.data?.jours[0] ?? null;
  const g = useApi<GridDay>(current ? `/api/grid/${current}` : null);

  if (idx.error) return <ErrorBox error={idx.error} />;
  if (!idx.data) return <Loading height={480} />;
  const s = idx.data.resume;
  const pm = s.pointe_moyenne_MW;
  const strategies = [
    { key: "pratique_actuelle", name: "Pratique actuelle", tone: "ink3", dash: "solid", width: 2 },
    { key: "tarif_seul", name: "Réponse au tarif seul", tone: "ink2", dash: "dashed", width: 2 },
    { key: "voltEye_grid", name: "VoltEye Grid", tone: "accent", dash: "solid", width: 3 },
  ] as const;

  return (
    <>
      <PageTitle kicker={`${s.zones} zones industrielles · ${nf(s.usines, 0)} usines · été 2026`} title="VoltEye Grid">
        L'été, la demande dépasse la capacité du réseau l'après-midi. VoltEye connaît, usine par usine, les charges qui
        peuvent attendre quelques heures : il les répartit pour abaisser la pointe vue par le réseau, sans changer
        l'énergie consommée.
      </PageTitle>

      <div className="grid gap-4">
        <Module title={`Pointe agrégée moyenne · ${s.jours_evalues} jours ouvrés les plus chargés`}>
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <Stat value={nf(pm.pratique_actuelle, 1)} unit="MW" caption="pratique actuelle" />
            <Stat value={nf(pm.tarif_seul, 1)} unit="MW" caption="chaque usine suit le tarif seule : la pointe se déplace" />
            <Stat value={nf(pm.voltEye_grid, 1)} unit="MW" caption="démarrages coordonnés par VoltEye Grid" tone="good" />
            <Stat value={`−${nf(s.effacement_MW_vs_pratique, 1)}`} unit="MW" caption={`soit ${nf(s["effacement_%_vs_pratique"], 1)} % de la pointe ; −${nf(s.effacement_MW_vs_tarif_seul, 1)} MW face au tarif seul`} tone="good" />
          </div>
        </Module>

        <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
          <Module
            title="Demande des 10 zones heure par heure"
            aside={
              <label className="flex items-center gap-2 text-sm">
                Jour
                <select className="rounded border border-edge bg-module-2 px-2 py-1" value={current ?? ""} onChange={(e) => setDay(e.target.value)}>
                  {idx.data.jours.map((j) => <option key={j} value={j}>{fmtDay(j)}</option>)}
                </select>
              </label>
            }
          >
            {g.error ? <ErrorBox error={g.error} /> : !g.data ? <Loading height={320} /> : (
              <>
                <Chart
                  label="Demande agrégée des 10 zones sur 24 heures selon trois stratégies"
                  height={320}
                  deps={[current, g.data]}
                  option={(p) => ({
                    tooltip: { valueFormatter: (v: number) => `${nf(v, 1)} MW` },
                    xAxis: { type: "category", data: Array.from({ length: 24 }, (_, h) => `${h} h`), axisLabel: { interval: 2 } },
                    yAxis: { type: "value", name: "MW", min: 0 },
                    series: strategies.map((st) => {
                      const col = st.tone === "accent" ? p.accent : st.tone === "ink2" ? p.ink2 : p.ink3;
                      const sd = g.data![st.key];
                      return {
                        name: `${st.name} (${nf(sd.pointe_MW, 1)} MW)`, type: "line", step: "end", symbol: "none",
                        lineStyle: { width: st.width, type: st.dash, color: col }, itemStyle: { color: col },
                        data: sd.profil_MW,
                        markPoint: { symbol: "circle", symbolSize: 9, itemStyle: { color: col, borderColor: p.module, borderWidth: 2 }, label: { show: false }, data: [{ coord: [`${sd.heure_pointe} h`, sd.pointe_MW] }] },
                      };
                    }),
                  })}
                />
                <p className="mt-2 text-sm text-ink-2">
                  Quand chaque usine vise seule l'heure la moins chère, toutes basculent au même moment : la pointe se
                  reforme à {g.data.tarif_seul.heure_pointe} h. VoltEye Grid étale ces démarrages entre les zones.
                </p>
              </>
            )}
          </Module>

          <Module title="Flexibilité par zone" aside={<ToggleTable show={table} onChange={setTable} />}>
            {table ? (
              <Table
                caption="Zones industrielles et leur flexibilité"
                head={["Zone", "Secteur", "Usines", "Pointe", "Flexibilité"]}
                rows={idx.data.zones.map((z) => [
                  <span className={active === z.site ? "font-bold" : ""}>{z.site}</span>, z.secteur, <span className="num">{z.usines}</span>,
                  <span className="num">{nf(z.pointe_MW, 1)} MW</span>, <span className="num">{nf(z.flexibilite_MW, 1)} MW</span>,
                ])}
              />
            ) : (
              <>
                <ZoneMap zones={idx.data.zones} active={active} onPick={setActive} />
                <p className="mt-2 text-center text-xs text-ink-3">Taille du cercle : flexibilité inscrite au programme ({nf(s.participation * 100, 0)} % des usines).</p>
                {active && (() => {
                  const z = idx.data!.zones.find((x) => x.site === active)!;
                  return (
                    <dl className="mt-3 grid grid-cols-2 gap-2 rounded-md bg-module-2 p-3 text-sm">
                      <dt className="text-ink-2">Zone</dt><dd className="font-bold">{z.site}</dd>
                      <dt className="text-ink-2">Secteur</dt><dd>{z.secteur} · {z.usines} usines</dd>
                      <dt className="text-ink-2">Pointe</dt><dd className="num">{nf(z.pointe_MW, 1)} MW</dd>
                      <dt className="text-ink-2">Flexibilité</dt><dd className="num">{nf(z.flexibilite_MW, 1)} MW</dd>
                      <dt className="text-ink-2">Gain planning</dt><dd className="num">{nf(z.gain_planification_TND_an / 1000, 0)} k TND / an</dd>
                    </dl>
                  );
                })()}
              </>
            )}
          </Module>
        </div>
      </div>
    </>
  );
}
