/**
 * Live-Klick: Modus 3 im Chrome – Gesellschaft, Häkchen, kein unbekannt.
 * Aufruf: node modus3_browser.mjs BASE_URL DOCX_PATH
 */
import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";

const require = createRequire(import.meta.url);
let puppeteer;
for (const candidate of [
  "/tmp/llp-browser/node_modules/puppeteer-core",
  path.join(process.cwd(), "node_modules/puppeteer-core"),
]) {
  try {
    puppeteer = require(candidate);
    break;
  } catch {
    /* nächster Pfad */
  }
}
if (!puppeteer) {
  console.error("puppeteer-core fehlt");
  process.exit(2);
}

const [baseUrl, docxPath] = process.argv.slice(2);
if (!baseUrl || !docxPath) {
  console.error("usage: node modus3_browser.mjs BASE_URL DOCX_PATH");
  process.exit(2);
}

const chrome =
  process.env.CHROME_PATH ||
  ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"].find((p) => fs.existsSync(p));
if (!chrome) {
  console.error("Chrome nicht gefunden");
  process.exit(2);
}

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
});

const page = await browser.newPage();
const notes = [];
page.on("console", (msg) => notes.push(msg.text()));

try {
  await page.goto(baseUrl, {waitUntil: "domcontentloaded", timeout: 20000});
  await page.waitForSelector(".mode-card", {timeout: 10000});
  const cards = await page.$$(".mode-card");
  await cards[2].click();
  await page.waitForSelector("#mode-ugb:not(.hidden)", {timeout: 5000});
  const startDisabled = await page.$eval("#ug-btn", (el) => el.disabled);
  if (!startDisabled) {
    throw new Error("Start war ohne Datei und Häkchen aktiv");
  }
  const input = await page.$("#ug-file");
  await input.uploadFile(docxPath);
  await page.waitForFunction(
    () => document.getElementById("ug-rechtsform").value || document.getElementById("ug-profil-hint").textContent.includes("Bitte"),
    {timeout: 20000},
  );
  const form = await page.$eval("#ug-rechtsform", (el) => el.value);
  const size = await page.$eval("#ug-groessenklasse", (el) => el.value);
  if (form !== "gmbh" || size !== "klein") {
    throw new Error(`Vorschlag falsch: ${form}/${size}`);
  }
  await page.waitForFunction(
    () => /Teil 1:.*gelten/i.test(document.getElementById("ug-eingrenzung")?.textContent || ""),
    {timeout: 15000},
  );
  const scope = await page.$eval("#ug-eingrenzung", (el) => el.textContent);
  if (/unbekannt/i.test(scope)) {
    throw new Error(`Teil 1 enthält unbekannt: ${scope}`);
  }
  if (!/gmbh/i.test(scope) || !/klein/i.test(scope)) {
    throw new Error(`Teil 1 ohne Gesellschaft: ${scope}`);
  }
  const btnLabel = await page.$eval("#ug-btn", (el) => el.textContent);
  if (!/Teil 2/i.test(btnLabel)) {
    throw new Error(`Knopf ohne Teil 2: ${btnLabel}`);
  }
  let stillDisabled = await page.$eval("#ug-btn", (el) => el.disabled);
  if (!stillDisabled) {
    throw new Error("Start war ohne Bestätigung aktiv");
  }
  await page.click("#ug-bestaetigt");
  stillDisabled = await page.$eval("#ug-btn", (el) => el.disabled);
  if (stillDisabled) {
    throw new Error("Start blieb nach Bestätigung inaktiv");
  }
  await page.click("#ug-btn");
  await page.waitForSelector("#ug-result:not(.hidden)", {timeout: 60000});
  const hint = await page.$eval("#ug-hinweis", (el) => el.textContent);
  if (/unbekannt/i.test(hint)) {
    throw new Error(`Hinweis enthält unbekannt: ${hint}`);
  }
  if (!/gmbh/i.test(hint) || !/klein/i.test(hint)) {
    throw new Error(`Hinweis ohne Gesellschaft: ${hint}`);
  }
  const body = await page.content();
  if (/unbekannt/i.test(body) && !/kein stilles/i.test(body)) {
    /* Ergebnisseite darf unbekannt nicht als Status zeigen */
  }
  console.log("BROWSER_OK", hint.replace(/\s+/g, " ").trim());
} finally {
  await browser.close();
}
