import fs from "node:fs/promises";
import path from "node:path";
import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE_ROOT = path.resolve(process.env.PRIMCOM_SITE_ROOT || ROOT);
const LIVE_REGISTRY_PATH = path.resolve(process.env.SEO_REGISTRY_PATH || path.join(ROOT, "seo", "content-registry.json"));
const LIVE_STATE_PATH = path.resolve(process.env.SEO_LASTMOD_STATE || path.join(path.dirname(LIVE_REGISTRY_PATH), "lastmod-state.json"));
const LOCK_PATH = path.join(SITE_ROOT, ".primcom-seo-publish.lock");

async function acquireLock() {
  const deadline = Date.now() + 120_000;
  while (true) {
    try {
      await fs.mkdir(LOCK_PATH);
      await fs.writeFile(path.join(LOCK_PATH, "owner.json"), JSON.stringify({pid:process.pid, createdAt:new Date().toISOString()}));
      return;
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      try {
        const stat = await fs.stat(LOCK_PATH);
        if (Date.now() - stat.mtimeMs > 10 * 60_000) {
          await fs.rm(LOCK_PATH, {recursive:true, force:true});
          continue;
        }
      } catch {}
      if (Date.now() >= deadline) throw new Error("SEO publish lock timeout");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
}

await acquireLock();
let stageRoot = "";
try {
  stageRoot = await fs.mkdtemp(path.join(SITE_ROOT, ".primcom-seo-stage-"));
} catch (error) {
  await fs.rm(LOCK_PATH, {recursive:true, force:true});
  throw error;
}
const outputRoot = path.join(stageRoot, "site");
const registryPath = path.join(stageRoot, "content-registry.json");

function run(script, env = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(ROOT, "scripts", script)], {
      cwd:ROOT,
      env:{...process.env, ...env},
      stdio:"inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${script} exited with code ${code}`)));
  });
}

async function exists(target) {
  try { await fs.access(target); return true; } catch { return false; }
}

const swapped = [];
const swappedFiles = [];
const backupRoot = path.join(stageRoot, "backup");

try {
  await fs.mkdir(outputRoot, {recursive:true});
  await run("sync-seo-catalog.mjs", {
    SEO_REGISTRY_PATH:LIVE_REGISTRY_PATH,
    SEO_REGISTRY_OUTPUT:registryPath,
  });
  await run("generate-seo-pages.mjs", {SEO_OUTPUT_ROOT:outputRoot, SEO_REGISTRY_PATH:registryPath, SEO_SITE_ROOT:SITE_ROOT, SEO_LASTMOD_STATE:LIVE_STATE_PATH});
  await run("check-seo-pages.mjs", {SEO_OUTPUT_ROOT:outputRoot, SEO_SITE_ROOT:SITE_ROOT, SEO_REGISTRY_PATH:registryPath});

  await fs.mkdir(backupRoot, {recursive:true});
  for (const name of ["cars", "guides"]) {
    const live = path.join(SITE_ROOT, name);
    const staged = path.join(outputRoot, name);
    const backup = path.join(backupRoot, name);
    const hadLive = await exists(live);
    if (hadLive) await fs.rename(live, backup);
    try {
      await fs.rename(staged, live);
    } catch (error) {
      if (hadLive && await exists(backup)) await fs.rename(backup, live);
      throw error;
    }
    swapped.push({live, backup});
  }

  const sitemapTmp = path.join(SITE_ROOT, `.sitemap.${process.pid}.tmp`);
  const registryTmp = path.join(path.dirname(LIVE_REGISTRY_PATH), `.content-registry.${process.pid}.tmp`);
  await fs.copyFile(path.join(outputRoot, "sitemap.xml"), sitemapTmp);
  const stateTmp = path.join(path.dirname(LIVE_STATE_PATH), `.lastmod-state.${process.pid}.tmp`);
  await fs.copyFile(registryPath, registryTmp);
  await fs.copyFile(path.join(outputRoot, "lastmod-state.json"), stateTmp);
  for (const [temporary, live, backupName] of [
    [sitemapTmp, path.join(SITE_ROOT, "sitemap.xml"), "sitemap.xml"],
    [registryTmp, LIVE_REGISTRY_PATH, "content-registry.json"],
    [stateTmp, LIVE_STATE_PATH, "lastmod-state.json"],
  ]) {
    const backup = path.join(backupRoot, backupName);
    const hadLive = await exists(live);
    if (hadLive) await fs.rename(live, backup);
    try {
      await fs.rename(temporary, live);
    } catch (error) {
      if (hadLive && await exists(backup)) await fs.rename(backup, live);
      throw error;
    }
    swappedFiles.push({live, backup});
  }
  console.log(JSON.stringify({status:"published", siteRoot:SITE_ROOT, registry:LIVE_REGISTRY_PATH}));
} catch (error) {
  for (const {live, backup} of swappedFiles.reverse()) {
    await fs.rm(live, {force:true});
    if (await exists(backup)) await fs.rename(backup, live);
  }
  for (const {live, backup} of swapped.reverse()) {
    await fs.rm(live, {recursive:true, force:true});
    if (await exists(backup)) await fs.rename(backup, live);
  }
  throw error;
} finally {
  await fs.rm(stageRoot, {recursive:true, force:true});
  await fs.rm(LOCK_PATH, {recursive:true, force:true});
}
