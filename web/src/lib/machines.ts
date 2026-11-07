// Ordre fixe de la palette catégorielle (validée) : il sert aussi d'ordre d'empilement des graphiques.
export const MACHINES = ["compresseur", "four", "cvc", "eclairage", "soudage", "cnc", "convoyeur"] as const;
export type MachineType = (typeof MACHINES)[number];

export const LABELS: Record<string, string> = {
  compresseur: "Compresseur d'air",
  four: "Four",
  cvc: "Climatisation",
  eclairage: "Éclairage",
  soudage: "Soudage",
  cnc: "Machine CNC",
  convoyeur: "Convoyeur",
};

export const TECH: Record<string, string> = {
  compresseur: "moteur asynchrone",
  four: "résistances",
  cvc: "compresseur inverter",
  eclairage: "drivers LED",
  soudage: "onduleur",
  cnc: "variateur de vitesse",
  convoyeur: "moteur direct",
};

export const CAUSES: Record<string, string> = {
  hors_production: "Consommation hors production",
  production: "Surconsommation en production",
  pic: "Pic horaire anormal",
  sous_consommation: "Arrêt ou sous-consommation",
};

export const machineVar = (m: string) => `--m-${m}`;
export const label = (m: string | null | undefined) => (m ? LABELS[m] ?? m : "Inconnue");
