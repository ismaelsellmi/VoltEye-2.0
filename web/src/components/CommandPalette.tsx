import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { CornerDownLeft, Search, type LucideIcon } from "lucide-react";

export type Command = {
  id: string;
  label: string;
  group: string;
  /** Autres mots qui doivent la retrouver (« réseau » pour VoltEye Grid). */
  keywords?: string[];
  hint?: string;
  icon?: LucideIcon;
  run: () => void;
};

// Recherche insensible aux accents et à la casse. Classement : le libellé commence par la saisie,
// puis un mot du libellé, puis n'importe où, puis les mots-clés ; l'ordre déclaré départage.
const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

function rank(c: Command, q: string) {
  const l = fold(c.label);
  const at = l.indexOf(q);
  if (at === 0) return 0;
  if (at > 0) return /[\s\-/'·]/.test(l[at - 1]) ? 1 : 2;
  return c.keywords?.some((k) => fold(k).includes(q)) ? 3 : -1;
}

/** Palette de commandes (Ctrl K / ⌘ K) : aller à une page, changer de thème, poser une question à l'assistant.
 *  Boîte de dialogue native (focus piégé, Échap), liste au clavier avec surlignage qui glisse. */
export function CommandPalette({
  open,
  onOpenChange,
  commands,
  extra,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  commands: Command[];
  /** Commandes construites à partir de la saisie (ex. « Demander à l'assistant »). */
  extra?: (query: string) => Command[];
}) {
  const id = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [hl, setHl] = useState<{ y: number; h: number } | null>(null);
  const pressedBackdrop = useRef(false);

  const groups = useMemo(() => {
    const q = fold(query.trim());
    const list = q
      ? commands
          .map((c, i) => ({ c, r: rank(c, q), i }))
          .filter((m) => m.r >= 0)
          .sort((a, b) => a.r - b.r || a.i - b.i)
          .map((m) => m.c)
      : commands;
    const all = [...list, ...(q && extra ? extra(query.trim()) : [])];
    const map = new Map<string, Command[]>();
    for (const c of all) map.set(c.group, [...(map.get(c.group) ?? []), c]);
    return [...map];
  }, [commands, extra, query]);
  const flat = useMemo(() => groups.flatMap(([, cs]) => cs), [groups]);
  const optionId = (c: Command) => `${id}-${c.id}`;

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) {
      setQuery("");
      setActive(0);
      d.showModal();
    } else if (!open && d.open) d.close();
  }, [open]);

  useEffect(() => setActive(0), [query]);

  useLayoutEffect(() => {
    const c = flat[active];
    const el = c && results.current?.querySelector<HTMLElement>(`#${CSS.escape(optionId(c))}`);
    if (!el) {
      setHl(null);
      return;
    }
    setHl({ y: el.offsetTop, h: el.offsetHeight });
    el.scrollIntoView({ block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, flat, open]);

  const run = (c: Command | undefined) => {
    if (!c) return;
    dialog.current?.close();
    c.run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;
    const n = flat.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (n) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : -1) + n) % n);
    } else if (e.key === "Home") {
      setActive(0);
    } else if (e.key === "End") {
      setActive(Math.max(0, n - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(flat[active]);
    }
  };

  return (
    <dialog
      ref={dialog}
      className="palette glass-strong"
      aria-label="Palette de commandes"
      onClose={() => onOpenChange(false)}
      onPointerDown={(e) => (pressedBackdrop.current = e.target === dialog.current)}
      onClick={(e) => {
        if (pressedBackdrop.current && e.target === dialog.current) dialog.current?.close();
      }}
    >
      <div className="flex items-center gap-3 border-b border-edge px-4">
        <Search size={18} className="shrink-0 text-ink-3" aria-hidden />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded="true"
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={flat[active] ? optionId(flat[active]) : undefined}
          aria-label="Rechercher une page, une action ou poser une question"
          autoComplete="off"
          spellCheck={false}
          placeholder="Aller à une page, changer de thème, poser une question…"
          className="h-14 min-w-0 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none"
        />
        <kbd className="hidden sm:inline">Échap</kbd>
      </div>

      <div ref={results} className="relative max-h-[min(420px,60vh)] overflow-y-auto overscroll-contain p-2">
        {hl && (
          <span
            aria-hidden
            className="absolute inset-x-2 top-0 rounded-xl bg-accent/12 ring-1 ring-accent/25 transition-[transform,height] duration-150 ease-out"
            style={{ transform: `translateY(${hl.y}px)`, height: hl.h }}
          />
        )}
        <div id={`${id}-list`} role="listbox" aria-label="Résultats">
          {groups.map(([name, cs]) => (
            <div key={name} role="group" aria-labelledby={`${id}-g-${name}`}>
              <div id={`${id}-g-${name}`} className="label-strip px-3 pb-1.5 pt-3">
                {name}
              </div>
              {cs.map((c) => {
                const Icon = c.icon;
                const selected = flat[active] === c;
                return (
                  <div
                    key={c.id}
                    id={optionId(c)}
                    role="option"
                    aria-selected={selected}
                    tabIndex={-1}
                    onPointerMove={() => setActive(flat.indexOf(c))}
                    onPointerDown={(e) => e.preventDefault()}
                    onClick={() => run(c)}
                    className={`relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] ${selected ? "text-ink" : "text-ink-2"}`}
                  >
                    {Icon && (
                      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-edge ${selected ? "bg-accent text-white" : "bg-module-2 text-ink-2"}`}>
                        <Icon size={16} aria-hidden />
                      </span>
                    )}
                    <span className="min-w-0 flex-1 truncate font-semibold">{c.label}</span>
                    {c.hint && <span className="hidden shrink-0 text-xs text-ink-3 sm:inline">{c.hint}</span>}
                    {selected && <CornerDownLeft size={15} className="shrink-0 text-ink-3" aria-hidden />}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        {!flat.length && <p className="px-3 py-8 text-center text-sm text-ink-3">Aucun résultat pour « {query} ».</p>}
      </div>
      <div className="flex items-center gap-4 border-t border-edge px-4 py-2.5 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1.5"><kbd>↑</kbd><kbd>↓</kbd> parcourir</span>
        <span className="inline-flex items-center gap-1.5"><kbd>Entrée</kbd> ouvrir</span>
      </div>
      <p role="status" className="sr-only">
        {query.trim() ? `${flat.length} résultat${flat.length > 1 ? "s" : ""}` : ""}
      </p>
    </dialog>
  );
}
