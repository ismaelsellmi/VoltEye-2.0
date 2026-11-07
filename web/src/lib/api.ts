import { useQuery } from "@tanstack/react-query";

export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError("Serveur VoltEye injoignable. Vérifiez que l'API tourne (docker compose up).");
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(`${r.status} : ${detail}`);
  }
  return r.json() as Promise<T>;
}

export function useApi<T>(path: string | null, staleTime = 60_000) {
  return useQuery({ queryKey: [path], queryFn: () => api<T>(path as string), enabled: !!path, staleTime });
}

// --- Formes renvoyées par l'API -------------------------------------------------------

export type Machine = { mtype: string; name: string; label: string; p_rated_kw: number; pf: number };

export type Kpis = {
  periode: { fin: string; jours: number };
  energie_kWh: number;
  cout_TND: number;
  co2_kg: number;
  repartition: { mtype: string; kwh: number }[];
  alertes_recentes: { day: string; mtype: string; score: number; cause: string; excess_cost_tnd: number | null }[];
  sante: { mtype: string; health: number; drift: number; alert: boolean; days_left: number | null }[];
  modeles: { reconnaissance_exactitude: number; anomalies_f1_test: number; prevision_mape: number; anticipation_panne_jours: number };
  planning: { "gain_moyen_%": number; gain_annuel_estime_TND: number; reduction_pointe_moyenne_kW: number };
  grid: { effacement_MW_vs_pratique: number; "effacement_%_vs_pratique": number; usines: number; zones: number };
};

export type AnomalyDay = {
  day: string;
  mtype: string;
  energy_kwh: number;
  expected_kwh: number | null;
  score: number | null;
  alert: boolean;
  cause: string | null;
  excess_cost_tnd: number | null;
  period: string | null;
  recommandation: string | null;
};

export type HealthDay = { day: string; mtype: string; thd: number; drift: number | null; health: number | null; days_left: number | null; alert: boolean };

export type ForecastPoint = { time: string; p10: number | null; p50: number; p90: number | null; actual: number; baseline: number | null };

export type Task = { nom: string; kW: number; duree: number; fenetre: [number, number]; demarrage?: number };

export type ScheduleDay = {
  jour: string;
  base: number[];
  prix: number[];
  ref: number[];
  opt: number[];
  operateur?: number[];
  facture_ref_TND: number;
  facture_opt_TND: number;
  facture_operateur_TND?: number;
  pointe_ref_kW: number;
  pointe_opt_kW: number;
  pointe_operateur_kW?: number;
};

export type Strategy = { profil_MW: number[]; pointe_MW: number; heure_pointe: number; cout_kTND: number };
export type GridDay = { jour: string; statut: string; base_MW: number[]; pratique_actuelle: Strategy; tarif_seul: Strategy; voltEye_grid: Strategy };
export type Zone = {
  site: string; lat: number; lon: number; secteur: string; usines: number; consommation_MWh_an: number; pointe_MW: number;
  flexibilite_MW: number; "part_hors_production_%": number; gain_planification_TND_an: number; sante_moyenne: number;
};
export type GridSummary = {
  zones: number; usines: number; participation: number; jours_evalues: number; flexibilite_MW: number;
  pointe_moyenne_MW: { pratique_actuelle: number; tarif_seul: number; voltEye_grid: number };
  effacement_MW_vs_pratique: number; "effacement_%_vs_pratique": number;
  effacement_MW_vs_tarif_seul: number; "effacement_%_vs_tarif_seul": number; energie_deplacee_MWh_jour: number;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;
