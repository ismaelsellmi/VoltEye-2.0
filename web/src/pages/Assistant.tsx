import { useEffect, useRef, useState } from "react";
import { api, useApi, type Json } from "../lib/api";
import { Module, PageTitle } from "../components/ui";

type Step = { outil: string; arguments: Json; resultat?: string };
type Answer = { reponse: string; etapes: Step[]; sources: string[]; mode: string };
type Turn = { q: string; a?: Answer; error?: string };

const EXAMPLES = [
  "Combien la fuite d'air de février nous a-t-elle coûté, et que faut-il faire ?",
  "Quelle machine consomme le plus, et combien hors production ?",
  "Quel est l'état de santé du convoyeur ?",
  "Combien de mégawatts VoltEye Grid efface-t-il pendant la pointe d'été ?",
];

export default function Assistant() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const state = useApi<{ mode: string; modele: string | null; evaluation: Json }>("/api/assistant/etat");
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
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
    }
  };

  return (
    <>
      <PageTitle kicker="Questions en langage naturel · réponses chiffrées par les outils VoltEye" title="Assistant énergie">
        L'assistant ne devine aucun chiffre : il appelle les fonctions de VoltEye (anomalies, santé, prévision, planning,
        VoltEye Grid) et cherche dans la documentation approuvée, puis cite ses sources.
      </PageTitle>

      <Module
        title="Conversation"
        aside={state.data && (
          <span className="text-xs text-ink-3">
            {state.data.mode === "llm" ? `Modèle ${state.data.modele}` : "Mode hors ligne"}
            {state.data.evaluation && ` · ${state.data.evaluation.reponses_justes}/${state.data.evaluation.questions} réponses justes à l'évaluation`}
          </span>
        )}
      >
        <div className="space-y-5">
          {!turns.length && (
            <div>
              <p className="mb-2 text-sm text-ink-2">Exemples de questions :</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((e) => (
                  <button key={e} onClick={() => ask(e)} className="rounded-full border border-edge bg-module-2 px-3 py-1.5 text-left text-sm hover:border-accent">
                    {e}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className="space-y-2">
              <p className="ml-auto max-w-[85%] w-fit rounded-lg rounded-br-sm bg-accent px-3 py-2 text-accent-ink">{t.q}</p>
              {t.a?.etapes.map((s, j) => (
                <p key={j} className="num w-fit max-w-full truncate border-l-2 border-edge pl-2 text-xs text-ink-3" title={JSON.stringify(s.arguments)}>
                  outil → {s.outil}({Object.entries(s.arguments ?? {}).map(([k, v]) => `${k} = ${v}`).join(", ")})
                </p>
              ))}
              {t.a && (
                <div className="max-w-[90%] rounded-lg rounded-bl-sm border border-edge bg-module-2 px-3 py-2">
                  <p className="whitespace-pre-line">{t.a.reponse}</p>
                  {t.a.sources.length > 0 && <p className="mt-2 text-xs text-ink-3">Sources : {t.a.sources.join(" · ")}</p>}
                  {t.a.mode !== "llm" && <p className="mt-1 text-xs text-ink-3">Mode hors ligne : réponse construite directement à partir des outils.</p>}
                </div>
              )}
              {t.error && <p role="alert" className="text-sm text-critical">{t.error}</p>}
              {!t.a && !t.error && <p className="text-sm text-ink-3">L'assistant interroge les outils VoltEye…</p>}
            </div>
          ))}
          <div ref={end} />
        </div>
        <form
          className="mt-5 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            ask(q);
          }}
        >
          <label htmlFor="question" className="sr-only">Votre question</label>
          <input
            id="question"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Posez une question sur l'énergie du site…"
            className="min-w-0 flex-1 rounded-md border border-edge bg-module-2 px-3 py-2"
          />
          <button disabled={busy || !q.trim()} className="rounded-md bg-accent px-4 py-2 font-bold text-accent-ink disabled:opacity-50">
            Envoyer
          </button>
        </form>
      </Module>
    </>
  );
}
