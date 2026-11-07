import type { ReactNode } from "react";
import { label, machineVar } from "../lib/machines";

/** Module fixé sur le rail de l'armoire : une bande d'étiquette dit ce qu'il mesure. */
export function Module({ title, aside, children, className = "", id }: { title: string; aside?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={`min-w-0 rounded-lg border border-edge bg-module shadow-[0_1px_0_var(--rail)] ${className}`}>
      <header className="flex min-h-10 flex-wrap items-center justify-between gap-2 border-b border-edge px-4 py-2">
        <h2 className="label-strip">{title}</h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageTitle({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 max-w-3xl">
      <p className="label-strip">{kicker}</p>
      <h1 className="font-display text-4xl font-bold uppercase leading-none tracking-wide sm:text-5xl">{title}</h1>
      {children && <p className="mt-2 text-ink-2">{children}</p>}
    </div>
  );
}

/** Lecture façon afficheur : grand chiffre condensé, unité, légende. */
export function Stat({ value, unit, caption, tone }: { value: string; unit?: string; caption: string; tone?: "good" | "critical" }) {
  const color = tone === "good" ? "text-good" : tone === "critical" ? "text-critical" : "text-ink";
  return (
    <div className="min-w-0">
      <div className={`reading text-4xl ${color}`}>
        {value}
        {unit && <span className="ml-1 font-sans text-base font-normal text-ink-3">{unit}</span>}
      </div>
      <p className="mt-1 text-sm text-ink-2">{caption}</p>
    </div>
  );
}

export function MachineDot({ m, size = 10 }: { m: string; size?: number }) {
  return <span aria-hidden className="inline-block shrink-0 rounded-sm" style={{ width: size, height: size, background: `var(${machineVar(m)})` }} />;
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
  good: { icon: "●", cls: "text-good", text: "Normal" },
  warning: { icon: "▲", cls: "text-warning", text: "À surveiller" },
  critical: { icon: "■", cls: "text-critical", text: "Alerte" },
};

/** État avec icône et texte : jamais la couleur seule. */
export function Status({ level, text }: { level: keyof typeof STATUS; text?: string }) {
  const s = STATUS[level];
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-bold ${s.cls}`}>
      <span aria-hidden>{s.icon}</span>
      {text ?? s.text}
    </span>
  );
}

export function Segmented<T extends string>({ value, options, onChange, ariaLabel }: { value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; ariaLabel: string }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex flex-wrap gap-1 rounded-md bg-module-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded px-2.5 py-1 text-sm transition-colors ${value === o.value ? "bg-module font-bold text-ink shadow-sm" : "text-ink-2 hover:text-ink"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Loading({ height = 200 }: { height?: number }) {
  return <div className="animate-pulse rounded-md bg-module-2" style={{ height }} aria-label="Chargement" />;
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div role="alert" className="rounded-md border border-critical/40 bg-critical/5 p-3 text-sm text-critical">
      {error instanceof Error ? error.message : "Erreur inattendue."}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-edge p-6 text-center">
      <p className="font-bold">{title}</p>
      {children && <div className="mt-1 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Table({ head, rows, caption }: { head: ReactNode[]; rows: ReactNode[][]; caption?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} className="border-b border-edge px-2 py-1.5 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-ink-3">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-edge/60 last:border-0">
              {r.map((c, j) => (
                <td key={j} className="px-2 py-1.5 align-top">
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
  return (
    <button onClick={() => onChange(!show)} className="text-sm text-accent underline-offset-2 hover:underline" aria-pressed={show}>
      {show ? "Voir le graphique" : "Voir le tableau"}
    </button>
  );
}
