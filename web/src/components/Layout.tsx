import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  BookOpen,
  Bell,
  BellOff,
  CalendarClock,
  Fingerprint,
  FlaskConical,
  LayoutDashboard,
  LayoutGrid,
  MapPin,
  Monitor,
  Moon,
  Search,
  Settings2,
  ShieldAlert,
  Sparkles,
  Sun,
  UtilityPole,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { MeterStrip } from "./MeterStrip";
import { BrandLoader, LogoMark } from "./Logo";
import { Backdrop } from "./Backdrop";
import { CommandPalette, type Command } from "./CommandPalette";
import { applyChoice, readChoice, type ThemeChoice } from "../lib/theme";
import { useLive } from "../lib/live";
import { nf } from "../lib/format";

type Page = { to: string; label: string; short: string; icon: LucideIcon; group: string; keywords: string[] };

// Trois groupes qui suivent le parcours : voir ce qui se passe, agir dessus, comprendre comment c'est calculé.
const NAV: Page[] = [
  { to: "/", label: "Vue d'ensemble", short: "Accueil", icon: LayoutDashboard, group: "Surveiller", keywords: ["accueil", "tableau de bord", "indicateurs"] },
  { to: "/direct", label: "Direct", short: "Direct", icon: Activity, group: "Surveiller", keywords: ["temps réel", "puissance", "compteur", "mesure"] },
  { to: "/reconnaissance", label: "Reconnaissance", short: "Signature", icon: Fingerprint, group: "Surveiller", keywords: ["signature", "forme d'onde", "gaf", "grad-cam"] },
  { to: "/anomalies", label: "Anomalies et santé", short: "Alertes", icon: ShieldAlert, group: "Surveiller", keywords: ["alertes", "gaspillage", "maintenance", "santé", "moteur"] },
  { to: "/prevision", label: "Prévision et planning", short: "Planning", icon: CalendarClock, group: "Optimiser", keywords: ["prévision", "shap", "solaire", "optimiseur", "facture"] },
  { to: "/grid", label: "VoltEye Grid", short: "Réseau", icon: UtilityPole, group: "Optimiser", keywords: ["réseau", "pointe", "zones industrielles", "carte"] },
  { to: "/assistant", label: "Assistant", short: "Assistant", icon: Sparkles, group: "Comprendre", keywords: ["question", "ia", "chat", "conversation"] },
  { to: "/evaluation", label: "Évaluation", short: "Évaluation", icon: FlaskConical, group: "Comprendre", keywords: ["méthodes", "résultats", "protocole", "hipe", "données"] },
];
const GROUPS = ["Surveiller", "Optimiser", "Comprendre"];
const MOBILE = ["/", "/direct", "/anomalies", "/assistant"];

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

const THEMES: { value: ThemeChoice; label: string; icon: LucideIcon }[] = [
  { value: "auto", label: "Système", icon: Monitor },
  { value: "light", label: "Clair", icon: Sun },
  { value: "dark", label: "Sombre", icon: Moon },
];

function Settings({ theme, setTheme }: { theme: ThemeChoice; setTheme: (c: ThemeChoice) => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { limit, enable } = usePowerAlert();
  const [draft, setDraft] = useState(String(limit ?? 60));
  const denied = typeof Notification !== "undefined" && Notification.permission === "denied";

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Réglages" title="Réglages" className="btn-ghost h-10 w-10 !p-0">
        <Settings2 size={18} aria-hidden />
      </button>
      {open && (
        <div className="pop glass-strong absolute right-0 top-12 z-40 w-[300px] rounded-2xl p-4">
          <p className="label-strip mb-2">Affichage</p>
          <div className="mb-5 grid grid-cols-3 gap-1 rounded-xl border border-edge bg-module-2 p-1">
            {THEMES.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                aria-pressed={theme === value}
                className={`flex flex-col items-center gap-1 rounded-lg px-2 py-2 text-xs font-semibold transition-colors ${theme === value ? "bg-accent text-accent-ink shadow-sm" : "text-ink-2 hover:text-ink"}`}
              >
                <Icon size={16} aria-hidden />
                {label}
              </button>
            ))}
          </div>
          <p className="label-strip mb-2">Alerte de puissance</p>
          <label className="mb-3 flex items-center gap-2 text-sm text-ink-2">
            Seuil
            <input type="number" min={1} value={draft} onChange={(e) => setDraft(e.target.value)} className="field num w-24" />
            kW
          </label>
          {limit ? (
            <button onClick={() => enable(null)} className="btn-ghost w-full">
              <BellOff size={16} aria-hidden />
              Désactiver l'alerte ({nf(limit, 0)} kW)
            </button>
          ) : (
            <button onClick={() => enable(Number(draft) || 60)} className="btn-primary w-full">
              <Bell size={16} aria-hidden />
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
    <div role="status" className="relative z-[2] mx-3 mt-3 flex items-center justify-center gap-2 rounded-xl bg-signal px-4 py-2 text-center text-sm font-bold text-signal-ink">
      <WifiOff size={16} aria-hidden />
      Hors connexion : les derniers chiffres consultés restent affichés.
    </div>
  );
}

const STATE_LABEL = { connexion: "Connexion…", "en direct": "Compteur en direct", muet: "Passerelle muette", "hors ligne": "Hors ligne" } as const;

function Sidebar() {
  const { state } = useLive();
  const live = state === "en direct";
  return (
    <aside className="glass sticky top-3 hidden h-[calc(100dvh-24px)] w-[252px] shrink-0 flex-col rounded-[22px] p-3 lg:flex">
      <NavLink to="/" className="flex items-center gap-2.5 rounded-xl px-2.5 py-2" aria-label="VoltEye, vue d'ensemble">
        <LogoMark live={live} className="h-7 w-auto text-ink" />
        <span className="font-display text-[26px] font-bold uppercase leading-none tracking-wide">VoltEye</span>
      </NavLink>

      <nav aria-label="Navigation principale" className="mt-4 min-h-0 flex-1 overflow-y-auto">
        {GROUPS.map((g) => (
          <div key={g} className="mb-4">
            <p className="label-strip px-3 pb-1.5">{g}</p>
            <ul className="space-y-0.5">
              {NAV.filter((n) => n.group === g).map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.to === "/"}
                    className={({ isActive }) =>
                      `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14.5px] transition-colors duration-200 ${
                        isActive ? "bg-module-2 font-bold text-ink shadow-[inset_0_0_0_1px_var(--edge)]" : "font-medium text-ink-2 hover:bg-module-2 hover:text-ink"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span aria-hidden className={`absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent transition-opacity ${isActive ? "opacity-100" : "opacity-0"}`} />
                        <n.icon size={18} aria-hidden className={isActive ? "text-accent" : "text-ink-3 transition-colors group-hover:text-ink-2"} />
                        {n.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="rounded-2xl border border-edge bg-module-2 p-3">
        <p className="flex items-center gap-2 text-sm font-bold">
          <MapPin size={15} className="text-ink-3" aria-hidden />
          Atelier de référence
        </p>
        <p className="mt-0.5 pl-[23px] text-xs text-ink-3">Ben Arous · compteur général</p>
        <p className="mt-2 flex items-center gap-2 pl-[23px] text-xs font-semibold text-ink-2">
          <span aria-hidden className={`h-2 w-2 rounded-full ${live ? "live-dot bg-signal" : state === "hors ligne" ? "bg-critical" : "bg-ink-3"}`} />
          {STATE_LABEL[state]}
        </p>
      </div>
      <p className="mt-3 px-2 text-[11px] leading-relaxed text-ink-3">Smart City Challenge 2026 · Track 2 · Intelligent Energy</p>
    </aside>
  );
}

function MobileNav({ onMenu }: { onMenu: () => void }) {
  return (
    <nav aria-label="Navigation" className="fixed inset-x-0 bottom-0 z-30 flex justify-center px-3 pb-[max(12px,env(safe-area-inset-bottom))] lg:hidden">
      <ul className="glass-strong flex items-center gap-1 rounded-full p-1.5">
        {NAV.filter((n) => MOBILE.includes(n.to)).map((n) => (
          <li key={n.to}>
            <NavLink
              to={n.to}
              end={n.to === "/"}
              aria-label={n.label}
              className={({ isActive }) =>
                `flex h-11 min-w-11 items-center justify-center rounded-full px-3 transition-colors duration-200 active:scale-95 ${isActive ? "bg-accent/15 text-accent" : "text-ink-2"}`
              }
            >
              {({ isActive }) => (
                <>
                  <n.icon size={20} aria-hidden />
                  <span className={`grid transition-[grid-template-columns,opacity,margin] duration-300 ease-out ${isActive ? "ml-2 grid-cols-[1fr] opacity-100" : "grid-cols-[0fr] opacity-0"}`}>
                    <span className="overflow-hidden whitespace-nowrap text-[13px] font-bold">{n.short}</span>
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
        <li>
          <button onClick={onMenu} aria-label="Toutes les pages et actions" className="flex h-11 min-w-11 items-center justify-center rounded-full px-3 text-ink-2 active:scale-95">
            <LayoutGrid size={20} aria-hidden />
          </button>
        </li>
      </ul>
    </nav>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  const [palette, setPalette] = useState(false);
  const [theme, setThemeState] = useState<ThemeChoice>(readChoice);
  const setTheme = useCallback((c: ThemeChoice) => {
    setThemeState(c);
    applyChoice(c);
  }, []);

  // Changement de page : titre de l'onglet, retour en haut, focus sur le contenu (lecteurs d'écran)
  useEffect(() => {
    const page = NAV.find((n) => n.to === pathname);
    document.title = page && page.to !== "/" ? `${page.label} · VoltEye` : "VoltEye · énergie industrielle";
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0 });
    main.current?.focus({ preventScroll: true });
  }, [pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey) && !e.altKey) {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const commands = useMemo<Command[]>(
    () => [
      ...NAV.map((n) => ({ id: `page${n.to.replace("/", "-")}`, label: n.label, group: "Pages", keywords: n.keywords, icon: n.icon, hint: n.group, run: () => navigate(n.to) })),
      ...THEMES.map((t) => ({ id: `theme-${t.value}`, label: `Thème ${t.label.toLowerCase()}`, group: "Affichage", keywords: ["thème", "mode", "couleurs", "clair", "sombre"], icon: t.icon, run: () => setTheme(t.value) })),
      { id: "docs", label: "Documentation de l'API", group: "Ressources", keywords: ["api", "openapi", "swagger", "développeur"], icon: BookOpen, hint: "/docs", run: () => window.open("/docs", "_blank", "noopener") },
    ],
    [navigate, setTheme],
  );
  const ask = useCallback(
    (q: string): Command[] => [{ id: "ask", label: `Demander à l'assistant : « ${q} »`, group: "Assistant", icon: Sparkles, run: () => navigate(`/assistant?q=${encodeURIComponent(q)}`) }],
    [navigate],
  );

  return (
    <div className="relative min-h-dvh">
      <a href="#contenu" className="btn-primary sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50">
        Aller au contenu
      </a>
      <Backdrop />
      <OfflineBanner />
      <div className="relative z-[1] mx-auto flex max-w-[1480px] gap-4 p-3 pb-28 lg:pb-3">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <header className="glass sticky top-3 z-20 flex items-center gap-2 rounded-[18px] px-2.5 py-2 sm:gap-3">
            <NavLink to="/" className="flex shrink-0 items-center gap-2 pl-1 lg:hidden" aria-label="VoltEye, vue d'ensemble">
              <LogoMark className="h-6 w-auto text-ink" />
              <span className="hidden font-display text-[22px] font-bold uppercase leading-none tracking-wide min-[420px]:inline">VoltEye</span>
            </NavLink>
            <MeterStrip />
            <button onClick={() => setPalette(true)} className="btn-ghost h-10 shrink-0 !px-2.5 xl:!px-3" aria-label="Rechercher une page ou une action" title="Rechercher (Ctrl K)">
              <Search size={18} aria-hidden />
              <span className="hidden text-sm xl:inline">Rechercher</span>
              <kbd className="hidden xl:inline">Ctrl K</kbd>
            </button>
            <Settings theme={theme} setTheme={setTheme} />
          </header>
          <main id="contenu" ref={main} tabIndex={-1} className="px-1 pt-7 outline-none sm:px-3">
            <Suspense fallback={<BrandLoader full={false} />}>
              <div key={pathname} className="page-enter">
                <Outlet />
              </div>
            </Suspense>
          </main>
        </div>
      </div>
      <MobileNav onMenu={() => setPalette(true)} />
      <CommandPalette open={palette} onOpenChange={setPalette} commands={commands} extra={ask} />
    </div>
  );
}
