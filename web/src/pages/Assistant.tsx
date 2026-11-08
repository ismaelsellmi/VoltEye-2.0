import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowUp, Coins, Gauge, HeartPulse, UtilityPole, Wrench, type LucideIcon } from "lucide-react";
import { api, useApi, type Json } from "../lib/api";
import { PageTitle } from "../components/ui";
import { LogoMark } from "../components/Logo";

type Step = { outil: string; arguments: Json; resultat?: string };
type Answer = { reponse: string; etapes: Step[]; sources: string[]; mode: string };
type Turn = { q: string; a?: Answer; error?: string };

const EXAMPLES: { q: string; icon: LucideIcon }[] = [
  { q: "Combien la fuite d'air de février nous a-t-elle coûté, et que faut-il faire ?", icon: Coins },
  { q: "Quelle machine consomme le plus, et combien hors production ?", icon: Gauge },
  { q: "Quel est l'état de santé du convoyeur ?", icon: HeartPulse },
  { q: "Combien de mégawatts VoltEye Grid efface-t-il pendant la pointe d'été ?", icon: UtilityPole },
];

export default function Assistant() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [params, setParams] = useSearchParams();
  const asked = useRef(false);
  const state = useApi<{ mode: string; modele: string | null; evaluation: Json }>("/api/assistant/etat");
  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setQ("");
    setBusy(true);
    const history = turns.filter((t) => t.a).flatMap((t) => [{ role: "user", content: t.q }, { role: "assistant", content: t.a!.reponse }]);
    setTurns((t) => [...t, { q: text }]);
    try {
      const a = await api<Answer>("/api/assistant", { method: "POST", body: JSON.stringify({ question: text, historique: history.slice(-6) }) });
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      const msg = e instanceof Error && e.message.startsWith("404") ? "L'assistant n'est pas encore activé sur ce serveur." : e instanceof Error ? e.message : "Erreur inattendue.";
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  };

  // Question envoyée depuis la palette de commandes (?q=…)
  useEffect(() => {
    const fromPalette = params.get("q");
    if (!fromPalette || asked.current) return;
    asked.current = true;
    setParams({}, { replace: true });
    ask(fromPalette);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ev = state.data?.evaluation;
  return (
    <>
      <PageTitle kicker="Questions en langage naturel · réponses chiffrées par les outils VoltEye" title="Assistant énergie">
        L'assistant ne devine aucun chiffre : il appelle les fonctions de VoltEye (anomalies, santé, prévision, planning,
        VoltEye Grid) et cherche dans la documentation approuvée, puis cite ses sources.
      </PageTitle>

      <section className="glass flex min-h-[min(640px,calc(100dvh-260px))] flex-col rounded-[22px]" aria-label="Conversation avec l'assistant">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-edge px-5 py-3">
          <h2 className="text-[15px] font-bold">Conversation</h2>
          {state.data && (
            <span className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full border border-edge bg-module-2 px-2.5 py-1 font-semibold text-ink-2">
                {state.data.mode === "llm" ? `Modèle ${state.data.modele}` : "Mode hors ligne"}
              </span>
              {ev && (
                <span className="rounded-full bg-good/12 px-2.5 py-1 font-bold text-good">
                  {ev.reponses_justes}/{ev.questions} réponses justes à l'évaluation
                </span>
              )}
            </span>
          )}
        </header>

        <div className="flex-1 space-y-6 px-5 py-6" aria-live="polite">
          {!turns.length && (
            <div className="mx-auto flex max-w-2xl flex-col items-center py-4 text-center">
              <LogoMark animated className="w-20 text-ink" />
              <p className="mt-4 text-xl font-extrabold tracking-[-0.02em]">Que voulez-vous savoir sur l'énergie du site ?</p>
              <p className="mt-1 text-sm text-ink-2">Choisissez une question ou écrivez la vôtre.</p>
              <div className="mt-6 grid w-full gap-2.5 sm:grid-cols-2">
                {EXAMPLES.map(({ q: e, icon: Icon }) => (
                  <button
                    key={e}
                    onClick={() => ask(e)}
                    className="group flex items-start gap-3 rounded-2xl border border-edge bg-module-2 p-3.5 text-left text-sm font-medium transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/50"
                  >
                    <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent/12 text-accent">
                      <Icon size={16} />
                    </span>
                    {e}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) => (
            <div key={i} className="space-y-3">
              <p className="pop ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-b from-[#2b78c9] to-[#1d5fa6] px-4 py-2.5 text-white shadow-[0_8px_20px_-10px_rgb(29_95_166/0.8)]">
                {t.q}
              </p>
              <div className="flex items-start gap-3">
                <span aria-hidden className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-edge bg-module-2">
                  <LogoMark live={!t.a && !t.error} className="w-5 text-ink" />
                </span>
                <div className="min-w-0 max-w-[90%] flex-1 space-y-2">
                  {t.a && t.a.etapes.length > 0 && (
                    <ul className="flex flex-wrap gap-1.5" aria-label="Outils appelés">
                      {t.a.etapes.map((s, j) => (
                        <li
                          key={j}
                          title={JSON.stringify(s.arguments)}
                          className="num inline-flex max-w-full items-center gap-1.5 truncate rounded-full border border-edge bg-module-2 px-2.5 py-1 text-[11.5px] text-ink-2"
                        >
                          <Wrench size={12} className="shrink-0 text-accent" aria-hidden />
                          <span className="truncate">
                            {s.outil}({Object.entries(s.arguments ?? {}).map(([k, v]) => `${k} = ${v}`).join(", ")})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {t.a && (
                    <div className="pop w-fit max-w-full rounded-2xl rounded-tl-md border border-edge bg-module-2 px-4 py-3">
                      <p className="whitespace-pre-line leading-relaxed">{t.a.reponse}</p>
                      {t.a.sources.length > 0 && (
                        <p className="mt-2.5 flex flex-wrap gap-1.5 text-xs text-ink-3">
                          <span className="font-semibold">Sources :</span>
                          {t.a.sources.map((s) => (
                            <span key={s} className="rounded-md bg-module px-1.5 py-0.5">{s}</span>
                          ))}
                        </p>
                      )}
                      {t.a.mode !== "llm" && <p className="mt-1.5 text-xs text-ink-3">Mode hors ligne : réponse construite directement à partir des outils.</p>}
                    </div>
                  )}
                  {t.error && <p role="alert" className="text-sm text-critical">{t.error}</p>}
                  {!t.a && !t.error && (
                    <p className="flex items-center gap-2.5 py-1.5 text-sm text-ink-3">
                      <span className="typing inline-flex gap-1 text-accent" aria-hidden><span /><span /><span /></span>
                      L'assistant interroge les outils VoltEye…
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={end} />
        </div>

        <form
          className="sticky bottom-24 border-t border-edge p-3 lg:bottom-3"
          onSubmit={(e) => {
            e.preventDefault();
            ask(q);
          }}
        >
          <div className="glass-strong flex items-end gap-2 rounded-2xl p-1.5 pl-4 focus-within:ring-2 focus-within:ring-accent/40">
            <label htmlFor="question" className="sr-only">Votre question</label>
            <textarea
              id="question"
              ref={input}
              rows={1}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(q);
                }
              }}
              placeholder="Posez une question sur l'énergie du site…"
              className="max-h-40 min-h-10 min-w-0 flex-1 resize-none bg-transparent py-2 text-[15px] text-ink outline-none focus-visible:outline-none [field-sizing:content] placeholder:text-ink-3"
            />
            <button disabled={busy || !q.trim()} className="btn-primary h-10 w-10 shrink-0 !rounded-xl !p-0" aria-label="Envoyer la question">
              <ArrowUp size={18} aria-hidden />
            </button>
          </div>
          <p className="mt-1.5 px-1 text-[11px] text-ink-3">Entrée pour envoyer · Maj + Entrée pour aller à la ligne</p>
        </form>
      </section>
    </>
  );
}
