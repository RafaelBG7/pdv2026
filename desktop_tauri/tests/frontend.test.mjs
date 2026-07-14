import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";

test("boot page has retry and browser fallback controls", async () => {
  const html = await readFile(new URL("../src/index.html", import.meta.url), "utf8");
  assert.match(html, /Tentar novamente/);
  assert.match(html, /Abrir no navegador/);
  assert.match(html, /main\.js/);
});

test("frontend invokes native health check before navigating", async () => {
  const js = await readFile(new URL("../src/main.js", import.meta.url), "utf8");
  assert.match(js, /get_desktop_config/);
  assert.match(js, /check_health/);
  assert.match(js, /window\.location\.replace/);
});
