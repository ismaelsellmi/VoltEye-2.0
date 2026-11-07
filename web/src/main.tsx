import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./index.css";
import { Layout } from "./components/Layout";
import { LiveProvider } from "./lib/live";
import { Loading } from "./components/ui";
import { applyChoice, readChoice } from "./lib/theme";

const Accueil = lazy(() => import("./pages/Accueil"));
const Direct = lazy(() => import("./pages/Direct"));
const Reconnaissance = lazy(() => import("./pages/Reconnaissance"));
const Anomalies = lazy(() => import("./pages/Anomalies"));
const Prevision = lazy(() => import("./pages/Prevision"));
const Grid = lazy(() => import("./pages/Grid"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Evaluation = lazy(() => import("./pages/Evaluation"));

applyChoice(readChoice());
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <LiveProvider>
        <BrowserRouter>
          <Suspense fallback={<div className="p-6"><Loading height={320} /></div>}>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Accueil />} />
                <Route path="direct" element={<Direct />} />
                <Route path="reconnaissance" element={<Reconnaissance />} />
                <Route path="anomalies" element={<Anomalies />} />
                <Route path="prevision" element={<Prevision />} />
                <Route path="grid" element={<Grid />} />
                <Route path="assistant" element={<Assistant />} />
                <Route path="evaluation" element={<Evaluation />} />
                <Route path="*" element={<Accueil />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </LiveProvider>
    </QueryClientProvider>
  </StrictMode>,
);
