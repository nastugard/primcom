// Единая команда для backend: собрать SEO-страницы и отправить изменения на хостинг.
//
//   SEO_PUBLISH_COMMAND=/usr/bin/node /opt/primcom/seo-publisher/scripts/publish-and-sync.mjs
//
// Сборка и отправка идут под одной блокировкой. Иначе вторая карточка, сохранённая
// сразу после первой, начала бы пересборку (она подменяет папки cars/ и guides/)
// в тот момент, когда первая ещё читает файлы для отправки.
import fs from "node:fs/promises";
import path from "node:path";
import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE_ROOT = path.resolve(process.env.PRIMCOM_SITE_ROOT || ROOT);
const LOCK_PATH = path.join(SITE_ROOT, ".primcom-publish-sync.lock");
// Дольше, чем ожидание блокировки самого публикатора (120 с), чтобы очередь не рвалась.
const LOCK_WAIT_MS = 240_000;
const LOCK_STALE_MS = 15 * 60_000;

async function acquireLock() {
  const deadline = Date.now() + LOCK_WAIT_MS;
  while (true) {
    try {
      await fs.mkdir(LOCK_PATH);
      return;
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      try {
        const stat = await fs.stat(LOCK_PATH);
        if (Date.now() - stat.mtimeMs > LOCK_STALE_MS) {
          await fs.rm(LOCK_PATH, {recursive:true, force:true});
          continue;
        }
      } catch { /* блокировку уже сняли */ }
      if (Date.now() >= deadline) throw new Error("publish-and-sync: не дождались освобождения блокировки");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
}

function runScript(script) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(ROOT, "scripts", script)], {cwd:ROOT, env:process.env, stdio:"inherit"});
    child.on("error", reject);
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${script} завершился с кодом ${code}`)));
  });
}

await acquireLock();
try {
  await runScript("publish-seo-catalog.mjs");
  await runScript("sync-to-host.mjs");
} catch (error) {
  console.error(`publish-and-sync: ${error.message}`);
  process.exitCode = 1;
} finally {
  await fs.rm(LOCK_PATH, {recursive:true, force:true});
}
