// Kopiert die benötigten Dateien der Frontend-Bibliotheken nach portal/static/vendor (nicht im Git).
// Aufruf: npm ci && npm run vendor   – im Docker-Build und einmalig für die lokale Entwicklung.
import { cpSync, mkdirSync, rmSync } from "node:fs";

const target = "portal/static/vendor";
const files = {
  "bootstrap/dist/css/bootstrap.min.css": "bootstrap/bootstrap.min.css",
  "bootstrap/dist/css/bootstrap.min.css.map": "bootstrap/bootstrap.min.css.map",
  "bootstrap/dist/js/bootstrap.bundle.min.js": "bootstrap/bootstrap.bundle.min.js",
  "bootstrap/dist/js/bootstrap.bundle.min.js.map": "bootstrap/bootstrap.bundle.min.js.map",
  "bootstrap-icons/font/bootstrap-icons.min.css": "bootstrap-icons/bootstrap-icons.min.css",
  "bootstrap-icons/font/fonts/bootstrap-icons.woff2": "bootstrap-icons/fonts/bootstrap-icons.woff2",
  "bootstrap-icons/font/fonts/bootstrap-icons.woff": "bootstrap-icons/fonts/bootstrap-icons.woff",
  "htmx.org/dist/htmx.min.js": "htmx/htmx.min.js",
  "@fontsource-variable/inter/files/inter-latin-wght-normal.woff2": "inter/inter-latin-wght-normal.woff2",
  "@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2": "inter/inter-latin-ext-wght-normal.woff2",
};

rmSync(target, { recursive: true, force: true });
for (const [from, to] of Object.entries(files)) {
  const dest = `${target}/${to}`;
  mkdirSync(dest.substring(0, dest.lastIndexOf("/")), { recursive: true });
  cpSync(`node_modules/${from}`, dest);
}
console.log(`Frontend-Bibliotheken nach ${target} kopiert.`);
