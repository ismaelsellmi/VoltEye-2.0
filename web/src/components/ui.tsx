import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ChartLine, CircleAlert, CircleCheck, Inbox, OctagonAlert, Table2, TriangleAlert, type LucideIcon } from "lucide-react";
import { label, machineVar } from "../lib/machines";
import { nf } from "../lib/format";

/** Panneau de verre : un titre qui dit ce qu'il montre, une zone d'action facultative à droite. */
export function Module({ title, aside, children, className = "", id, icon: Icon }: { title: string; aside?: ReactNode; children: ReactNode; className?: string; id?: string; icon?: LucideIcon }) {
  return (
    <section id={id} className={`glass min-w-0 rounded-[20px] ${className}`}>
      <header className="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-1 px-5 pt-4">
        <h2 className="flex items-center gap-2 text-[15px] font-bold tracking-[-0.01em] text-ink">
          {Icon && <Icon size={16} className="text-ink-3" aria-hidden />}
          {title}
        </h2>
        {aside && <div className="text-sm text-ink-2">{aside}</div>}
      </header>
      <div className="px-5 pb-5 pt-3">{children}</div>
    </section>
  );
}

export function PageTitle({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-7 max-w-3xl">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-ink-3">
        <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-signal shadow-[0_0_0_3px_rgb(242_194_0/0.22)]" />
        {kicker}
      </p>
      <h1 className="mt-2 text-[34px] font-extrabold leading-[1.05] tracking-[-0.028em] text-ink sm:text-[44px]">{title}</h1>
      {children && <p className="mt-3 text-[15.5px] leading-relaxed text-ink-2">{children}</p>}
    </div>
  );
}

// Nombre au format français en tête de texte (« 1 234,5 », « −12,3 % ») : animé de l'ancienne à la nouvelle valeur.
const NUM = /^([−-]?)(\d(?:[\d\u202f\u00a0 ]*\d)?)(?:,(\d+))?(\D*)$/;
const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function useCountUp(text: string) {
  const parsed = NUM.exec(text);
  const [shown, setShown] = useState(() => (parsed && !reduced() ? `${parsed[1]}${nf(0, parsed[3]?.length ?? 0)}${parsed[4]}` : text));
  const done = useRef<number | null>(null);
  useEffect(() => {
    const m = NUM.exec(text);
    if (!m || reduced()) {
      setShown(text);
      return;
    }
    const dec = m[3]?.length ?? 0;
    const target = Number(m[2].replace(/[\s\u202f\u00a0]/g, "") + (dec ? `.${m[3]}` : ""));
    const from = done.current ?? 0;
    if (from === target) {
      setShown(text);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 900);
      const e = 1 - Math.pow(1 - k, 3);
      if (k >= 1) {
        done.current = target;
        setShown(text);
        return;
      }
      setShown(`${m[1]}${nf(from + (target - from) * e, dec)}${m[4]}`);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text]);
  return shown;
}

/** Lecture façon afficheur : grand chiffre condensé qui se compte à l'apparition, unité, légende. */
export function Stat({ value, unit, caption, tone, icon: Icon }: { value: string; unit?: string; caption: string; tone?: "good" | "critical"; icon?: LucideIcon }) {
  const color = tone === "good" ? "text-good" : tone === "critical" ? "text-critical" : "text-ink";
  const shown = useCountUp(value);
  return (
    <div className="min-w-0 rounded-2xl border border-edge bg-module-2 p-4">
      {Icon && (
        <span aria-hidden className={`mb-3 grid h-8 w-8 place-items-center rounded-lg ${tone === "critical" ? "bg-critical/12 text-critical" : tone === "good" ? "bg-good/12 text-good" : "bg-accent/12 text-accent"}`}>
          <Icon size={16} />
        </span>
      )}
      <div className={`reading text-[40px] ${color}`}>
        <span aria-hidden>{shown}</span>
        <span className="sr-only">{value}</span>
        {unit && <span className="ml-1.5 font-sans text-[15px] font-semibold tracking-normal text-ink-3">{unit}</span>}
      </div>
      <p className="mt-1.5 text-[13.5px] leading-snug text-ink-2">{caption}</p>
    </div>
  );
}

export function MachineDot({ m, size = 10 }: { m: string; size?: number }) {
  return <span aria-hidden className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: `var(${machineVar(m)})`, boxShadow: `0 0 0 3px color-mix(in srgb, var(${machineVar(m)}) 18%, transparent)` }} />;
}

export function MachineName({ m, className = "" }: { m: string | null | undefined; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      {m && <MachineDot m={m} />}
      {label(m)}
    </span>
  );
}

const STATUS = {
  good: { Icon: CircleCheck, cls: "bg-good/12 text-good", text: "Normal" },
  warning: { Icon: TriangleAlert, cls: "bg-warning/12 text-warning", text: "À surveiller" },
  critical: { Icon: OctagonAlert, cls: "bg-critical/12 text-critical", text: "Alerte" },
};

/** État avec icône de forme distincte et texte : jamais la couleur seule. */
export function Status({ level, text }: { level: keyof typeof STATUS; text?: string }) {
  const s = STATUS[level];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${s.cls}`}>
      <s.Icon size={14} aria-hidden />
      {text ?? s.text}
    </span>
  );
}

/** Choix exclusif : un curseur glisse sous l'option choisie ; flèches du clavier pour changer. */
export function Segmented<T extends string>({ value, options, onChange, ariaLabel }: { value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; ariaLabel: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const root = wrap.current;
    if (!root) return;
    const measure = () => {
      const el = root.querySelector<HTMLElement>('[aria-checked="true"]');
      if (el) setBox({ x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, [value]);

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = options[(i + d + options.length) % options.length];
    onChange(next.value);
    requestAnimationFrame(() => wrap.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus());
  };

  return (
    <div ref={wrap} role="radiogroup" aria-label={ariaLabel} className="relative inline-flex flex-wrap gap-1 rounded-2xl border border-edge bg-module-2 p-1">
      {box && (
        <span
          aria-hidden
          className="glass-strong absolute left-0 top-0 rounded-xl !shadow-sm transition-[transform,width,height] duration-300 ease-[cubic-bezier(0.3,1.25,0.5,1)]"
          style={{ transform: `translate(${box.x}px, ${box.y}px)`, width: box.w, height: box.h }}
        />
      )}
      {options.map((o, i) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          tabIndex={value === o.value ? 0 : -1}
          onClick={() => onChange(o.value)}
          onKeyDown={(e) => onKey(e, i)}
          className={`relative rounded-xl px-3 py-1.5 text-sm transition-colors duration-200 ${value === o.value ? "font-bold text-ink" : "font-medium text-ink-2 hover:text-ink"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Loading({ height = 200 }: { height?: number }) {
  return <div className="skeleton rounded-2xl" style={{ height }} role="status" aria-label="Chargement" />;
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-2xl border border-critical/30 bg-critical/8 p-3.5 text-sm text-critical">
      <CircleAlert size={18} className="mt-px shrink-0" aria-hidden />
      <span>{error instanceof Error ? error.message : "Erreur inattendue."}</span>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-edge bg-module-2 px-6 py-10 text-center">
      <span aria-hidden className="mb-3 grid h-11 w-11 place-items-center rounded-xl border border-edge bg-module text-ink-3">
        <Inbox size={20} />
      </span>
      <p className="font-bold">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Table({ head, rows, caption }: { head: ReactNode[]; rows: ReactNode[][]; caption?: string }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full min-w-[480px] border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} className="border-b border-edge px-2.5 py-2 text-left text-[11px] font-bold uppercase tracking-[0.08em] text-ink-3">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-edge/70 transition-colors last:border-0 hover:bg-module-2">
              {r.map((c, j) => (
                <td key={j} className="px-2.5 py-2 align-top">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ToggleTable({ show, onChange }: { show: boolean; onChange: (v: boolean) => void }) {
  const Icon = show ? ChartLine : Table2;
  return (
    <button onClick={() => onChange(!show)} className="btn-ghost !py-1 !text-[13px]" aria-pressed={show}>
      <Icon size={14} aria-hidden />
      {show ? "Voir le graphique" : "Voir le tableau"}
    </button>
  );
}
