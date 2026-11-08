// Exporte les fichiers de la marque (brand/*.svg) en PNG : icônes de l'application, favicon, logos.
// Usage : npm run marque   (après python brand/generer_marque.py)
import { mkdirSync, readFileSync, copyFileSync, writeFileSync } from "node:fs";
import { Resvg } from "@resvg/resvg-js";

const brand = new URL("../../brand/", import.meta.url);
const icons = new URL("../public/icons/", import.meta.url);
const png = new URL("png/", brand);
mkdirSync(png, { recursive: true });

function render(svgName, outUrl, width) {
  const svg = readFileSync(new URL(svgName, brand), "utf8");
  const img = new Resvg(svg, { fitTo: { mode: "width", value: width } }).render();
  writeFileSync(outUrl, img.asPng());
  console.log(`${outUrl.pathname.split("/").slice(-2).join("/")}  ${img.width}x${img.height}`);
}

// Application web installable
render("volteye-icone.svg", new URL("icon-192.png", icons), 192);
render("volteye-icone.svg", new URL("icon-512.png", icons), 512);
render("volteye-icone-masquable.svg", new URL("icon-maskable-512.png", icons), 512);
render("volteye-icone-masquable.svg", new URL("apple-touch-icon.png", icons), 180);
render("volteye-favicon.svg", new URL("favicon-32.png", icons), 32);
copyFileSync(new URL("volteye-favicon.svg", brand), new URL("icon.svg", icons));

// Fichiers de marque prêts à l'emploi (présentations, rapport, Streamlit)
render("volteye-symbole.svg", new URL("volteye-symbole.png", png), 1024);
render("volteye-symbole-inverse.svg", new URL("volteye-symbole-inverse.png", png), 1024);
render("volteye-logo-horizontal.svg", new URL("volteye-logo-horizontal.png", png), 1600);
render("volteye-logo-horizontal-inverse.svg", new URL("volteye-logo-horizontal-inverse.png", png), 1600);
render("volteye-logo-empile.svg", new URL("volteye-logo-empile.png", png), 800);
render("volteye-icone.svg", new URL("volteye-icone.png", png), 1024);
render("volteye-favicon.svg", new URL("volteye-favicon-64.png", png), 64);
