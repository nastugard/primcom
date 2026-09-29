// Отправляет на хостинг только изменившиеся SEO-файлы: cars/, guides/ и sitemap.xml.
//
// Зачем: публикатор собирает страницы в локальную папку (PRIMCOM_SITE_ROOT), а сайт лежит
// на другой машине. Этот скрипт переносит результат, не трогая остальной сайт.
//
//   node scripts/sync-to-host.mjs            — отправить изменения
//   node scripts/sync-to-host.mjs --dry-run  — показать план и ничего не отправлять
//
// Настройки читаются из файла sync.env (KEY=VALUE, права 600) — путь можно задать
// переменной PRIMCOM_SYNC_CONFIG. Пароль в логи и в аргументы процессов не попадает.
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE_ROOT = path.resolve(process.env.PRIMCOM_SITE_ROOT || ROOT);
const CONFIG_PATH = path.resolve(process.env.PRIMCOM_SYNC_CONFIG || path.join(ROOT, "sync.env"));
const MANIFEST_PATH = path.join(SITE_ROOT, ".primcom-sync-manifest.json");
const DRY_RUN = process.argv.includes("--dry-run");
const SYNC_DIRS = ["cars", "guides"];
const SYNC_FILES = ["sitemap.xml"];
// sitemap уходит последним: робот не должен увидеть адрес раньше, чем появится страница.
const LAST = "sitemap.xml";

function fail(message) {
  console.error(`sync-to-host: ${message}`);
  process.exit(1);
}

async function readConfig() {
  const cfg = {};
  try {
    const raw = await fs.readFile(CONFIG_PATH, "utf8");
    for (const line of raw.split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
      if (!match || line.trim().startsWith("#")) continue;
      cfg[match[1]] = match[2].replace(/^(["'])(.*)\1$/, "$2");
    }
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  // Переменные окружения перекрывают файл: так удобно тестировать.
  for (const [key, value] of Object.entries(process.env)) if (key.startsWith("SYNC_")) cfg[key] = value;
  return cfg;
}

async function walk(dir, base = dir) {
  const out = [];
  let entries;
  try { entries = await fs.readdir(dir, {withFileTypes:true}); } catch { return out; }
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(full, base));
    else if (entry.isFile()) out.push(path.relative(base, full).split(path.sep).join("/"));
  }
  return out;
}

async function sha1(file) {
  return crypto.createHash("sha1").update(await fs.readFile(file)).digest("hex");
}

async function loadManifest() {
  try { return JSON.parse(await fs.readFile(MANIFEST_PATH, "utf8")); } catch { return {}; }
}

function run(command, args, {input} = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {stdio:["pipe", "inherit", "inherit"]});
    child.on("error", (error) => reject(new Error(`не удалось запустить ${command}: ${error.message}`)));
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${command} завершился с кодом ${code}`)));
    child.stdin.end(input || "");
  });
}

const shellQuote = (value) => `"${String(value).replace(/(["\\])/g, "\\$1")}"`;

// --- транспорты -------------------------------------------------------------------------
// Каждый принимает {put:[относительные пути], remove:[относительные пути]}.

async function transportLocal(cfg, {put, remove}) {
  const remoteRoot = cfg.SYNC_REMOTE_ROOT;
  if (!remoteRoot) fail("для метода local нужен SYNC_REMOTE_ROOT");
  for (const rel of put) {
    const target = path.join(remoteRoot, rel);
    await fs.mkdir(path.dirname(target), {recursive:true});
    const temporary = `${target}.tmp-${process.pid}`;
    await fs.copyFile(path.join(SITE_ROOT, rel), temporary);
    await fs.rename(temporary, target);
  }
  for (const rel of remove) await fs.rm(path.join(remoteRoot, rel), {force:true});
}

function lftpScript(cfg, {put, remove}, {maskPassword = false} = {}) {
  const protocol = cfg.SYNC_PROTOCOL || "ftp";
  const port = cfg.SYNC_PORT ? ` -p ${cfg.SYNC_PORT}` : "";
  const password = maskPassword ? "********" : (cfg.SYNC_PASSWORD || "");
  const lines = [
    "set cmd:fail-exit yes",
    "set net:max-retries 3",
    "set net:reconnect-interval-base 3",
    "set net:timeout 25",
    "set xfer:use-temp-file yes",
    protocol === "ftp" ? "set ftp:ssl-allow yes" : "",
    protocol === "ftps" ? "set ftp:ssl-force yes" : "",
    `open -u ${shellQuote(cfg.SYNC_USER)},${shellQuote(password)}${port} ${protocol === "ftps" ? "ftp" : protocol}://${cfg.SYNC_HOST}`,
    cfg.SYNC_REMOTE_ROOT && cfg.SYNC_REMOTE_ROOT !== "/" ? `cd ${shellQuote(cfg.SYNC_REMOTE_ROOT)}` : "",
  ].filter(Boolean);
  const dirs = [...new Set(put.map((rel) => path.posix.dirname(rel)).filter((dir) => dir !== "."))].sort();
  for (const dir of dirs) lines.push(`mkdir -p -f ${shellQuote(dir)}`);
  for (const rel of put) lines.push(`put -O ${shellQuote(path.posix.dirname(rel) === "." ? "." : path.posix.dirname(rel))} ${shellQuote(path.join(SITE_ROOT, rel))}`);
  for (const rel of remove) lines.push(`rm -f ${shellQuote(rel)}`);
  lines.push("bye");
  return lines.join("\n") + "\n";
}

async function transportLftp(cfg, plan) {
  for (const key of ["SYNC_HOST", "SYNC_USER", "SYNC_PASSWORD"]) if (!cfg[key]) fail(`для метода lftp нужен ${key}`);
  // Скрипт с паролем — во временный файл с правами 600: так пароль не виден в `ps`.
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "primcom-lftp-"));
  const file = path.join(dir, "commands.lftp");
  try {
    await fs.writeFile(file, lftpScript(cfg, plan), {mode:0o600});
    await run("lftp", ["-f", file]);
  } finally {
    await fs.rm(dir, {recursive:true, force:true});
  }
}

async function transportRsync(cfg, {put, remove}) {
  for (const key of ["SYNC_HOST", "SYNC_USER", "SYNC_REMOTE_ROOT"]) if (!cfg[key]) fail(`для метода rsync нужен ${key}`);
  const ssh = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"];
  if (cfg.SYNC_PORT) ssh.push("-p", cfg.SYNC_PORT);
  if (cfg.SYNC_SSH_KEY) ssh.push("-i", cfg.SYNC_SSH_KEY);
  const target = `${cfg.SYNC_USER}@${cfg.SYNC_HOST}:${cfg.SYNC_REMOTE_ROOT.replace(/\/?$/, "/")}`;
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "primcom-rsync-"));
  try {
    if (put.length) {
      const list = path.join(dir, "put.txt");
      await fs.writeFile(list, put.join("\n") + "\n");
      await run("rsync", ["-a", "-e", ssh.join(" "), `--files-from=${list}`, `${SITE_ROOT}/`, target]);
    }
    if (remove.length) {
      const list = path.join(dir, "remove.txt");
      await fs.writeFile(list, remove.join("\n") + "\n");
      await run("rsync", ["-a", "--delete-missing-args", "-e", ssh.join(" "), `--files-from=${list}`, `${SITE_ROOT}/`, target]);
    }
  } finally {
    await fs.rm(dir, {recursive:true, force:true});
  }
}

const TRANSPORTS = {local:transportLocal, lftp:transportLftp, rsync:transportRsync};

// --- основной ход -------------------------------------------------------------------------

const cfg = await readConfig();
const method = (cfg.SYNC_METHOD || "").toLowerCase();
if (!TRANSPORTS[method]) fail(`SYNC_METHOD должен быть local, lftp или rsync (сейчас: "${cfg.SYNC_METHOD || ""}"). Настройки читаются из ${CONFIG_PATH}`);

const current = {};
for (const dir of SYNC_DIRS) {
  for (const rel of await walk(path.join(SITE_ROOT, dir), SITE_ROOT)) current[rel] = await sha1(path.join(SITE_ROOT, rel));
}
for (const rel of SYNC_FILES) {
  try { current[rel] = await sha1(path.join(SITE_ROOT, rel)); } catch { /* файла может не быть */ }
}

if (!current[LAST]) fail(`нет ${LAST} в ${SITE_ROOT}: похоже, сборка не выполнялась. Ничего не отправлено.`);
const pageCount = Object.keys(current).filter((rel) => rel.endsWith(".html")).length;
if (pageCount < 20) fail(`в ${SITE_ROOT} всего ${pageCount} страниц: сборка выглядит неполной. Ничего не отправлено.`);

const manifest = await loadManifest();
const changed = Object.keys(current).filter((rel) => manifest[rel] !== current[rel]).sort();
const removed = Object.keys(manifest).filter((rel) => !(rel in current)).sort();

// Защита, как у синхронизации каталога: массовое удаление на хосте — это потеря страниц из индекса.
const removalLimit = Math.max(5, Math.floor(Object.keys(manifest).length * 0.2));
if (removed.length > removalLimit && cfg.SYNC_ALLOW_MASS_DELETE !== "1") {
  fail(`к удалению ${removed.length} файлов при лимите ${removalLimit}: похоже на сбой сборки. Ничего не изменено. Для намеренного удаления задайте SYNC_ALLOW_MASS_DELETE=1.`);
}

if (!changed.length && !removed.length) {
  console.log(JSON.stringify({status:"unchanged", files:Object.keys(current).length}));
  process.exit(0);
}

const phases = [
  {name:"pages", put:changed.filter((rel) => rel !== LAST), remove:[]},
  {name:"sitemap", put:changed.filter((rel) => rel === LAST), remove:[]},
  {name:"cleanup", put:[], remove:removed},
].filter((phase) => phase.put.length || phase.remove.length);

if (DRY_RUN) {
  console.log(JSON.stringify({status:"dry-run", method, changed:changed.length, removed:removed.length, phases:phases.map((p) => ({name:p.name, put:p.put.length, remove:p.remove.length}))}, null, 2));
  if (method === "lftp") for (const phase of phases) console.log(`--- lftp: ${phase.name} ---\n${lftpScript(cfg, phase, {maskPassword:true})}`);
  process.exit(0);
}

// Вход в манифест обновляем только после успешной отправки всех этапов: при сбое
// следующий запуск повторит то же самое, а повторная отправка безопасна.
for (const phase of phases) await TRANSPORTS[method](cfg, phase);

const temporary = `${MANIFEST_PATH}.${process.pid}.tmp`;
await fs.writeFile(temporary, JSON.stringify(current, null, 1));
await fs.rename(temporary, MANIFEST_PATH);
console.log(JSON.stringify({status:"synced", method, uploaded:changed.length, removed:removed.length}));
