/**
 * Live-Klick: Text verbessern nur Foundry, ohne stillen Wechsel, Beenden.
 * Aufruf: node text_foundry_browser.mjs BASE_URL
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

const [baseUrl] = process.argv.slice(2);
const chrome =
  process.env.CHROME_PATH ||
  ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"].find((p) => fs.existsSync(p));
if (!baseUrl || !chrome) {
  console.error("usage: node text_foundry_browser.mjs BASE_URL");
  process.exit(2);
}

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
try {
  await page.goto(baseUrl, {waitUntil: "domcontentloaded", timeout: 20000});
  await page.waitForSelector("#run", {timeout: 5000});
  const body = await page.$eval("body", (el) => el.innerText);
  if (!/foundry/i.test(body) || !/kein mistral/i.test(body)) {
    throw new Error("Seite nennt Foundry/Mistral nicht klar");
  }
  await page.type("#quelle", "Bitte diesen Satz klarer machen.");
  await page.click("#run");
  await page.waitForFunction(
    () => document.getElementById("fehler").textContent.trim().length > 0,
    {timeout: 10000},
  );
  const err = await page.$eval("#fehler", (el) => el.textContent);
  if (!/foundry/i.test(err)) {
    throw new Error(`Fehler ohne Foundry: ${err}`);
  }
  if (!/mistral|ollama/i.test(err)) {
    throw new Error(`Fehler verschweigt den nicht-Wechsel: ${err}`);
  }
  await page.click("#quit");
  await page.waitForFunction(
    () => /beendet/i.test(document.body.innerText),
    {timeout: 5000},
  );
  console.log("BROWSER_OK", err.replace(/\s+/g, " ").trim());
} finally {
  await browser.close();
}
