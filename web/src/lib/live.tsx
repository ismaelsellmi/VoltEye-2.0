import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";

export type Measure = { time: string; p_kw: number; q_kvar: number; pf: number; thd: number; estime: Record<string, number>; verite?: Record<string, number> };
export type LiveEvent = {
  time: string;
  direction: string;
  delta_kw: number;
  mtype: string | null;
  confiance: number | null;
  proba: Record<string, number>;
  verite?: string | null;
  waveform?: number[] | null;
};
export type LinkState = "connexion" | "en direct" | "muet" | "hors ligne";

type Live = { measures: Measure[]; events: LiveEvent[]; state: LinkState; last?: Measure };

const WINDOW_S = 900;          // 15 minutes de mesures gardées en mémoire
const SILENT_MS = 8000;        // au-delà, la passerelle est considérée muette
const Ctx = createContext<Live>({ measures: [], events: [], state: "connexion" });

export const useLive = () => useContext(Ctx);

// Les mesures REST et WebSocket n'ont pas tout à fait les mêmes noms de champs : on les harmonise ici.
/* eslint-disable @typescript-eslint/no-explicit-any */
const normMeasure = (m: any): Measure => ({ ...m, estime: m.estime ?? m.estimated ?? {} });
const normEvent = (e: any): LiveEvent => ({ ...e, confiance: e.confiance ?? e.confidence ?? null, proba: e.proba ?? {} });
/* eslint-enable @typescript-eslint/no-explicit-any */

export function LiveProvider({ site = "usine-ref", children }: { site?: string; children: ReactNode }) {
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [state, setState] = useState<LinkState>("connexion");
  const lastMsg = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 1000;
    let stopped = false;
    let timer: number | undefined;

    api<unknown[]>(`/api/direct?site=${site}&secondes=${WINDOW_S}`)
      .then((rows) => setMeasures(rows.map(normMeasure)))
      .catch(() => setState("hors ligne"));
    api<unknown[]>(`/api/evenements?site=${site}&limite=40&formes_onde=true`)
      .then((rows) => setEvents(rows.map(normEvent)))
      .catch(() => undefined);

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws/direct`);
      ws.onopen = () => {
        retry = 1000;
        setState("muet");
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.site !== site) return;
        lastMsg.current = Date.now();
        setState("en direct");
        if (msg.type === "mesure") {
          const m = normMeasure(msg);
          setMeasures((prev) => {
            const next = [...prev, m];
            const cutoff = new Date(m.time).getTime() - WINDOW_S * 1000;
            let i = 0;
            while (i < next.length && new Date(next[i].time).getTime() < cutoff) i++;
            return i ? next.slice(i) : next;
          });
        } else if (msg.type === "evenement") {
          setEvents((prev) => [normEvent(msg), ...prev].slice(0, 60));
        }
      };
      ws.onclose = () => {
        if (stopped) return;
        setState("hors ligne");
        timer = window.setTimeout(connect, retry);
        retry = Math.min(retry * 2, 15000);
      };
    };
    connect();
    const watchdog = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN && Date.now() - lastMsg.current > SILENT_MS) setState("muet");
    }, 2000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      window.clearInterval(watchdog);
      ws?.close();
    };
  }, [site]);

  return <Ctx.Provider value={{ measures, events, state, last: measures[measures.length - 1] }}>{children}</Ctx.Provider>;
}
