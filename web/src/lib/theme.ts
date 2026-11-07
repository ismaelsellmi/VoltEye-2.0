import { useEffect, useState } from "react";

export type ThemeChoice = "auto" | "light" | "dark";

const KEY = "volteye-theme";

export function readChoice(): ThemeChoice {
  try {
    return (localStorage.getItem(KEY) as ThemeChoice) || "auto";
  } catch {
    return "auto";
  }
}

export function applyChoice(c: ThemeChoice) {
  const root = document.documentElement;
  if (c === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", c);
  try {
    localStorage.setItem(KEY, c);
  } catch {
    /* stockage indisponible : le choix vaut pour la session */
  }
  window.dispatchEvent(new Event("volteye-theme"));
}

function resolved(): "light" | "dark" {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Thème effectif ; se met à jour quand l'utilisateur ou le système change de mode. */
export function useResolvedTheme() {
  const [t, setT] = useState(resolved);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setT(resolved());
    mq.addEventListener("change", on);
    window.addEventListener("volteye-theme", on);
    return () => {
      mq.removeEventListener("change", on);
      window.removeEventListener("volteye-theme", on);
    };
  }, []);
  return t;
}

/** Valeur calculée d'une variable CSS (les graphiques canvas ont besoin de couleurs explicites). */
export function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
