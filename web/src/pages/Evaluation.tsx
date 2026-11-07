import { useApi, type Json } from "../lib/api";
import { ErrorBox, Loading, Module, PageTitle, Table } from "../components/ui";
import { fmtDay, nf, pct } from "../lib/format";

const bold = (k: string) => k.startsWith("VoltEye") || k.startsWith("D -");
const name = (k: string) => k.replace("Baseline - ", "Référence : ").replace("Variante - ", "Variante : ");

export default function Evaluation() {
  const { data: e, error, isLoading } = useApi<Json>("/api/evaluation");
  const assistant = useApi<Json>("/api/assistant/etat");
  if (error) return <ErrorBox error={error} />;
  if (isLoading || !e) return <Loading height={600} />;
  const an = e.anomalies;
  const fl = e.flux;
  const op = e.optimisation;
  const gr = e.grid;
  const hp = e.hipe;

  return (
    <>
      <PageTitle kicker="Données, méthodes et résultats" title="Évaluation">
        Chaque modèle est mesuré sur des données qu'il n'a jamais vues et comparé à une méthode simple de référence. Les
        résultats ci-dessous sont produits par le code du dépôt (<span className="num">python -m volteye.pipeline</span>).
      </PageTitle>

      <div className="grid gap-4 xl:grid-cols-2">
        <Module title="Reconnaissance des machines · formes d'onde simulées">
          <Table
            head={["Approche", "Exactitude", "Bruit × 3", "ms / événement"]}
            rows={Object.entries(e.reconnaissance.models as Record<string, Json>).map(([k, v]) => [
              <span className={bold(k) ? "font-bold" : ""}>{k}</span>, <span className="num">{pct(v.accuracy)}</span>,
              <span className="num">{pct(v.accuracy_bruit_x3)}</span>, <span className="num">{nf(v.ms_par_evenement, 2)}</span>,
            ])}
          />
        </Module>

        <Module title="Désagrégation du flux temps réel">
          <Table
            head={["Scénario", "Détection F1", "Reconnaissance", "Précision énergétique"]}
            rows={[
              [`4 h, ${fl.evenements_reels} événements`, <span className="num">{nf(fl.detection_f1, 3)}</span>, <span className="num">{pct(fl.classification_exactitude)}</span>, <span className="num">{pct(fl.precision_energetique)}</span>],
              ...(fl.scenario_dense ? [[`Dense : ${fl.scenario_dense.evenements_reels} événements en 1 h`, <span className="num">{nf(fl.scenario_dense.detection_f1, 3)}</span>, <span className="num">{pct(fl.scenario_dense.classification_exactitude)}</span>, <span className="num">{pct(fl.scenario_dense.precision_energetique)}</span>]] : []),
            ]}
          />
        </Module>

        <Module title="Prévision du lendemain">
          <Table
            head={["Méthode", "Erreur moyenne", "Erreur en %"]}
            rows={Object.entries(e.prevision.models as Record<string, Json>).map(([k, v]) => [
              <span className={bold(k) ? "font-bold" : ""}>{name(k)}</span>, <span className="num">{nf(v.MAE_kWh, 2)} kWh</span>, <span className="num">{nf(v["MAPE_%_heures_actives"], 1)} %</span>,
            ])}
          />
          <p className="mt-2 text-xs text-ink-3">Test : {fmtDay(e.prevision.periode_test[0])} – {fmtDay(e.prevision.periode_test[1])}, jamais vu à l'entraînement.</p>
          {e.prevision.quantiles && (
            <p className="mt-1 text-sm">Fourchette P10–P90 conforme : <b className="num">{pct(e.prevision.quantiles.couverture_P10_P90)}</b> des heures réelles couvertes (cible 80 %).</p>
          )}
        </Module>

        <Module title="Détection des gaspillages · test sur 4 mois jamais vus">
          <Table
            head={["Méthode", "Seuil", "Précision", "Rappel", "F1"]}
            rows={Object.entries(an.models as Record<string, Json>).map(([k, v]) => [
              <span className={bold(k) ? "font-bold" : ""}>{name(k)}</span>, <span className="num">{nf(an.seuils?.[k], 2)}</span>,
              <span className="num">{nf(v.precision, 2)}</span>, <span className="num">{nf(v.rappel, 2)}</span>, <span className="num font-bold">{nf(v.f1, 2)}</span>,
            ])}
          />
          {an.protocole && (
            <p className="mt-2 text-xs text-ink-3">
              Réentraînement {an.protocole.reentrainement} ; normalisation : {an.protocole.normalisation}. Test :
              {" "}{an.protocole.jours_test} jours-machine dont {an.protocole.jours_anormaux_test} anormaux.
            </p>
          )}
        </Module>

        <Module title="Maintenance prédictive et optimisation">
          <ul className="space-y-2 text-[15px]">
            <li>Panne du convoyeur annoncée <b>{an.maintenance.anticipation_panne_convoyeur_jours} jours</b> avant, {an.maintenance.fausses_alertes_autres_machines_jours} jour de fausse alerte sur les autres machines.</li>
            <li>Planning optimisé : <b>−{nf(op["gain_moyen_%"], 1)} %</b> sur la facture et −{nf(op.reduction_pointe_moyenne_kW, 0)} kW de pointe face à la pratique actuelle, sur {op.jours_optimises} jours ouvrés.</li>
            {op.reference_operateur_averti && (
              <li>Face à un opérateur qui suit déjà le tarif : −{nf(op.reference_operateur_averti["gain_moyen_%"], 1)} % et −{nf(op.reference_operateur_averti.reduction_pointe_moyenne_kW, 1)} kW, grâce à la coordination des tâches.</li>
            )}
          </ul>
        </Module>

        <Module title="VoltEye Grid · pointe d'été">
          <Table
            head={["Stratégie", "Pointe moyenne"]}
            rows={[
              ["Pratique actuelle", <span className="num">{nf(gr.pointe_moyenne_MW.pratique_actuelle, 1)} MW</span>],
              ["Réponse au tarif seul", <span className="num">{nf(gr.pointe_moyenne_MW.tarif_seul, 1)} MW</span>],
              [<b>VoltEye Grid</b>, <span className="num font-bold">{nf(gr.pointe_moyenne_MW.voltEye_grid, 1)} MW</span>],
            ]}
          />
          <p className="mt-2 text-xs text-ink-3">
            {gr.zones} zones, {nf(gr.usines, 0)} usines, {nf(gr.participation * 100, 0)} % de participation ; {gr.jours_evalues} jours ouvrés les plus chargés de l'été, demande réelle simulée.
          </p>
        </Module>

        {assistant.data?.evaluation && (
          <Module title="Assistant énergie">
            <p className="text-[15px]">
              <b className="num">{assistant.data.evaluation.reponses_justes}/{assistant.data.evaluation.questions}</b> réponses justes et{" "}
              <b className="num">{assistant.data.evaluation.bon_outil}/{assistant.data.evaluation.questions}</b> bons outils sur le jeu de questions
              dont la réponse est calculée par les outils VoltEye (mode {assistant.data.evaluation.mode}).
            </p>
          </Module>
        )}

        {hp && (
          <Module title="Mesures industrielles réelles · HIPE (KIT)" className="xl:col-span-2">
            <p className="mb-3 text-sm text-ink-2">{hp.source}</p>
            <div className="grid gap-6 lg:grid-cols-2">
              <Table
                head={["Indicateur", "Valeur"]}
                rows={[
                  ["Signatures de 7 machines reconnues (P, Q, FP, harmoniques)", <span className="num font-bold">{pct(hp.signatures["VoltEye - + THD et harmoniques + forêt aléatoire"].exactitude)}</span>],
                  ["Même chose sans harmoniques", <span className="num">{pct(hp.signatures["A - P, Q, facteur de puissance + forêt aléatoire"].exactitude)}</span>],
                  ["Événements des machines suivies retrouvés à l'arrivée générale", <span className="num">{pct(hp.detection.rappel)}</span>],
                  ["Attribution des événements au point unique (avec harmoniques)", <span className="num">{pct(hp.reconnaissance["VoltEye - ΔP, ΔQ + harmoniques + forêt aléatoire"].exactitude)}</span>],
                ]}
              />
              <Table
                head={["Indicateur", "Valeur"]}
                rows={[
                  ["Prévision de la charge à 1 h (MAPE)", <span className="num font-bold">{nf(hp.prevision_1h["VoltEye - gradient boosting"]["MAPE_%"], 1)} %</span>],
                  ["Référence : valeur d'il y a 1 h", <span className="num">{nf(hp.prevision_1h["Baseline - valeur d'il y a 1 h"]["MAPE_%"], 1)} %</span>],
                  ["Énergie consommée hors production", <span className="num font-bold">{pct(hp.hors_production.MainTerminal.part_hors_production, 0)}</span>],
                  ["Talon du site, usine à l'arrêt", <span className="num">{nf(hp.hors_production.talon_site_kW, 1)} kW</span>],
                ]}
              />
            </div>
          </Module>
        )}
      </div>
    </>
  );
}
