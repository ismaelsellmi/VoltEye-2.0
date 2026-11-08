import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { MeterStrip } from "./MeterStrip";
import { LogoMark } from "./Logo";
import { applyChoice, readChoice, type ThemeChoice } from "../lib/theme";
import { useLive } from "../lib/live";
import { nf } from "../lib/format";

const NAV = [
  { to: "/", label: "Vue d'ensemble", short: "Accueil" },
  { to: "/direct", label: "Direct", short: "Direct" },
  { to: "/reconnaissance", label: "Reconnaissance", short: "Signature" },
  { to: "/anomalies", label: "Anomalies et santé", short: "Alertes" },
  { to: "/prevision", label: "Prévision et planning", short: "Planning" },
  { to: "/grid", label: "VoltEye Grid", short: "Réseau" },
  { to: "/assistant", label: "Assistant", short: "Assistant" },
  { to: "/evaluation", label: "Évaluation", short: "Évaluation" },
];
const MOBILE = ["/", "/direct", "/anomalies", "/grid", "/assistant"];

const LIMIT_KEY = "volteye-seuil-kw";

/** Alerte de dépassement de puissance sur ce téléphone ou cet ordinateur (notifications du navigateur). */
function usePowerAlert() {
  const { last } = useLive();
  const [limit, setLimit] = useState<number | null>(() => {
    try {
      const v = localStorage.getItem(LIMIT_KEY);
      return v ? Number(v) : null;
    } catch {
      return null;
    }
  });
  const lastSent = useRef(0);
  useEffect(() => {
    if (!limit || !last || last.p_kw <= limit || Date.now() - lastSent.current < 10 * 60_000) return;
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    lastSent.current = Date.now();
    const body = `${nf(last.p_kw, 1)} kW mesurés, au-dessus du seuil de ${nf(limit, 0)} kW.`;
    navigator.serviceWorker?.ready
      .then((r) => r.showNotification("VoltEye : dépassement de puissance", { body, tag: "volteye-seuil", icon: "/icons/icon-192.png" }))
      .catch(() => new Notification("VoltEye : dépassement de puissance", { body }));
  }, [last, limit]);

  const enable = async (kw: number | null) => {
    if (kw && "Notification" in window && Notification.permission === "default") await Notification.requestPermission();
    setLimit(kw);
    try {
      if (kw) localStorage.setItem(LIMIT_KEY, String(kw));
      else localStorage.removeItem(LIMIT_KEY);
    } catch {
      /* préférence non mémorisée */
    }
  };
  return { limit, enable };
}

function Settings() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeChoice>(readChoice);
  const { limit, enable } = usePowerAlert();
  const [draft, setDraft] = useState(String(limit ?? 60));
  const denied = typeof Notification !== "undefined" && Notification.permission === "denied";
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Réglages" className="rounded-md px-2 py-1.5 text-sm text-ink-2 hover:bg-module-2 hover:text-ink">
        <span className="hidden sm:inline">Réglages</span>
        <span aria-hidden className="text-lg leading-none sm:hidden">⚙</span>
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-30 w-72 rounded-lg border border-edge bg-module p-4 shadow-lg">
          <p className="label-strip mb-2">Affichage</p>
          <div className="mb-4 flex gap-1">
            {(["auto", "light", "dark"] as ThemeChoice[]).map((c) => (
              <button
                key={c}
                onClick={() => {
                  setTheme(c);
                  applyChoice(c);
                }}
                aria-pressed={theme === c}
                className={`flex-1 rounded px-2 py-1 text-sm ${theme === c ? "bg-accent text-accent-ink" : "bg-module-2 text-ink-2"}`}
              >
                {c === "auto" ? "Système" : c === "light" ? "Clair" : "Sombre"}
              </button>
            ))}
          </div>
          <p className="label-strip mb-2">Alerte de puissance</p>
          <label className="mb-2 flex items-center gap-2 text-sm">
            Seuil
            <input
              type="number"
              min={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="num w-20 rounded border border-edge bg-module-2 px-2 py-1"
            />
            kW
          </label>
          {limit ? (
            <button onClick={() => enable(null)} className="w-full rounded bg-module-2 px-2 py-1.5 text-sm">
              Désactiver l'alerte ({nf(limit, 0)} kW)
            </button>
          ) : (
            <button onClick={() => enable(Number(draft) || 60)} className="w-full rounded bg-accent px-2 py-1.5 text-sm font-bold text-accent-ink">
              Activer l'alerte sur cet appareil
            </button>
          )}
          {denied && <p className="mt-2 text-xs text-critical">Notifications bloquées : autorisez-les dans les réglages du navigateur.</p>}
        </div>
      )}
    </div>
  );
}

function OfflineBanner() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
    };
  }, []);
  if (online) return null;
  return (
    <div role="status" className="bg-signal px-4 py-1.5 text-center text-sm font-bold text-signal-ink">
      Hors connexion : les derniers chiffres consultés restent affichés.
    </div>
  );
}

export function Layout() {
  return (
    <div className="min-h-dvh pb-20 lg:pb-0">
      <OfflineBanner />
      <header className="sticky top-0 z-20 border-b border-edge bg-module/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-3 px-4 py-2">
          <NavLink to="/" className="flex shrink-0 items-center gap-2" aria-label="VoltEye, vue d'ensemble">
            <LogoMark className="h-7 w-auto text-ink" />
            <span className="hidden font-display text-2xl font-bold uppercase tracking-wide min-[400px]:inline">VoltEye</span>
          </NavLink>
          <span className="hidden shrink-0 border-l border-edge pl-3 text-sm text-ink-2 md:block">
            Atelier de référence
            <br />
            <span className="text-ink-3">Ben Arous · compteur général</span>
          </span>
          <MeterStrip />
          <Settings />
        </div>
      </header>
      <div className="mx-auto flex max-w-[1400px] gap-6 px-4 py-6">
        <nav aria-label="Navigation principale" className="sticky top-24 hidden h-fit w-52 shrink-0 lg:block">
          <ul className="space-y-0.5">
            {NAV.map((n) => (
              <li key={n.to}>
                <NavLink
                  to={n.to}
                  end={n.to === "/"}
                  className={({ isActive }) =>
                    `block rounded-md border-l-4 px-3 py-2 text-[15px] ${isActive ? "border-accent bg-module font-bold text-ink" : "border-transparent text-ink-2 hover:bg-module/60 hover:text-ink"}`
                  }
                >
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <p className="mt-6 px-3 text-xs leading-relaxed text-ink-3">
            Smart City Challenge 2026
            <br />
            Track 2 · Intelligent Energy
          </p>
        </nav>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
      <nav aria-label="Navigation" className="fixed inset-x-0 bottom-0 z-20 border-t border-edge bg-module pb-[env(safe-area-inset-bottom)] lg:hidden">
        <ul className="grid grid-cols-5">
          {NAV.filter((n) => MOBILE.includes(n.to)).map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) => `block border-t-2 px-1 py-2.5 text-center text-xs ${isActive ? "border-accent font-bold text-ink" : "border-transparent text-ink-2"}`}
              >
                {n.short}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
