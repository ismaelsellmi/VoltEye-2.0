// Extrait le contour de la Tunisie (Natural Earth 1:10m, via world-atlas) dans src/data/tunisia.json
import { readFileSync, writeFileSync } from "node:fs";
import { feature } from "topojson-client";

const topo = JSON.parse(readFileSync(new URL("../node_modules/world-atlas/countries-10m.json", import.meta.url)));
const tn = feature(topo, topo.objects.countries).features.find((f) => f.id === "788");
const round = (c) => (typeof c[0] === "number" ? [+c[0].toFixed(3), +c[1].toFixed(3)] : c.map(round));
const geom = { type: tn.geometry.type, coordinates: round(tn.geometry.coordinates) };
writeFileSync(new URL("../src/data/tunisia.json", import.meta.url), JSON.stringify(geom));
console.log(geom.type, JSON.stringify(geom).length, "octets");
