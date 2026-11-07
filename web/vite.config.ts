import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

// En développement, l'API FastAPI tourne sur le port 8000 (uvicorn ou docker compose).
const API = process.env.VOLTEYE_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon.svg"],
      manifest: {
        name: "VoltEye : énergie industrielle",
        short_name: "VoltEye",
        description: "Chaque machine vue depuis un seul compteur : direct, alertes, prévision, planning et pointe réseau.",
        lang: "fr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#dcded9",
        theme_color: "#1d5fa6",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api/, /^\/ws/, /^\/docs/, /^\/openapi\.json/],
        runtimeCaching: [
          {
            // Derniers chiffres consultés disponibles hors ligne (sauf le direct, qui n'a de sens qu'en ligne)
            urlPattern: /\/api\/(?!direct)/,
            handler: "NetworkFirst",
            method: "GET",
            options: {
              cacheName: "volteye-api",
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 300, maxAgeSeconds: 7 * 24 * 3600 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/api": API,
      "/ws": { target: API.replace(/^http/, "ws"), ws: true },
      "/docs": API,
      "/openapi.json": API,
    },
  },
  build: { chunkSizeWarningLimit: 1500 },
});
