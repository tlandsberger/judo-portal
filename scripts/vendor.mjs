// Kopiert die benötigten Dateien der Frontend-Bibliotheken nach portal/static/vendor (nicht im Git).
// Aufruf über `npm run vendor` (baut danach auch das CSS) – im Docker-Build und einmalig für die lokale Entwicklung.
import { cpSync, mkdirSync, rmSync } from "node:fs";

const target = "portal/static/vendor";
const files = {
  "bootstrap-icons/font/bootstrap-icons.min.css": "bootstrap-icons/bootstrap-icons.min.css",
  "bootstrap-icons/font/fonts/bootstrap-icons.woff2": "bootstrap-icons/fonts/bootstrap-icons.woff2",
  "bootstrap-icons/font/fonts/bootstrap-icons.woff": "bootstrap-icons/fonts/bootstrap-icons.woff",
  "htmx.org/dist/htmx.min.js": "htmx/htmx.min.js",
};

rmSync(target, { recursive: true, force: true });
for (const [from, to] of Object.entries(files)) {
  const dest = `${target}/${to}`;
  mkdirSync(dest.substring(0, dest.lastIndexOf("/")), { recursive: true });
  cpSync(`node_modules/${from}`, dest);
}
console.log(`Frontend-Bibliotheken nach ${target} kopiert.`);
