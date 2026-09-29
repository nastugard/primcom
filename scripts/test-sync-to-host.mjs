// Проверка отправки на хостинг на локальном транспорте: без сети и без реального сервера.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";

const SCRIPT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "sync-to-host.mjs");
const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "primcom-sync-test-"));
const site = path.join(tmp, "site");
const remote = path.join(tmp, "remote");

async function write(root, rel, content) {
  const file = path.join(root, rel);
  await fs.mkdir(path.dirname(file), {recursive:true});
  await fs.writeFile(file, content);
}

async function seedSite() {
  await fs.rm(site, {recursive:true, force:true});
  for (let i = 0; i < 40; i += 1) await write(site, `cars/japan/brand/model-${i}/index.html`, `<h1>model ${i}</h1><p>830000</p>`);
  await write(site, "guides/index.html", "<h1>guides</h1>");
  await write(site, "sitemap.xml", "<urlset/>");
  await write(site, ".primcom-seo-publish.lock/owner.json", "{}");   // служебное не должно уходить
}

const baseEnv = {...process.env, PRIMCOM_SITE_ROOT:site, PRIMCOM_SYNC_CONFIG:path.join(tmp, "absent.env"),
  SYNC_METHOD:"local", SYNC_REMOTE_ROOT:remote};
const sync = (extra = {}, args = []) => spawnSync(process.execPath, [SCRIPT, ...args], {env:{...baseEnv, ...extra}, encoding:"utf8"});
const exists = (rel) => fs.access(path.join(remote, rel)).then(() => true, () => false);

try {
  await seedSite();

  // 1. Первая отправка: всё, кроме служебных файлов.
  let result = sync();
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /"status":"synced"/);
  assert.match(result.stdout, /"uploaded":42/);
  assert.equal(await exists("sitemap.xml"), true);
  assert.equal(await exists("cars/japan/brand/model-3/index.html"), true);
  assert.equal(await exists(".primcom-seo-publish.lock/owner.json"), false, "служебные файлы не должны уходить на хост");

  // 2. Повторный запуск без изменений ничего не отправляет.
  result = sync();
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /"status":"unchanged"/);

  // 3. Цена 830000 -> 850000: размер файла тот же, но изменение должно заметиться.
  await write(site, "cars/japan/brand/model-7/index.html", "<h1>model 7</h1><p>850000</p>");
  result = sync();
  assert.match(result.stdout, /"uploaded":1/, "правка с тем же размером файла должна быть замечена");
  assert.match(await fs.readFile(path.join(remote, "cars/japan/brand/model-7/index.html"), "utf8"), /850000/);

  // 4. sitemap уходит отдельным, последним этапом.
  await write(site, "cars/japan/brand/model-9/index.html", "<h1>changed</h1>");
  await write(site, "sitemap.xml", "<urlset><url/></urlset>");
  result = sync({}, ["--dry-run"]);
  const plan = JSON.parse(result.stdout);
  assert.deepEqual(plan.phases.map((p) => p.name), ["pages", "sitemap"]);
  assert.equal(plan.phases[1].put, 1);
  result = sync();
  assert.match(result.stdout, /"uploaded":2/);

  // 5. Небольшое число удалённых файлов допустимо и удаляется на хосте.
  await fs.rm(path.join(site, "cars/japan/brand/model-1"), {recursive:true});
  result = sync();
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /"removed":1/);
  assert.equal(await exists("cars/japan/brand/model-1/index.html"), false);

  // 6. Массовое удаление блокируется, хост остаётся нетронутым.
  for (let i = 10; i < 20; i += 1) await fs.rm(path.join(site, `cars/japan/brand/model-${i}`), {recursive:true});
  result = sync();
  assert.notEqual(result.status, 0, "массовое удаление должно быть остановлено");
  assert.match(result.stderr, /похоже на сбой сборки/);
  assert.equal(await exists("cars/japan/brand/model-15/index.html"), true, "при блокировке хост не должен меняться");
  result = sync({SYNC_ALLOW_MASS_DELETE:"1"});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(await exists("cars/japan/brand/model-15/index.html"), false);

  // 7. Сборка без sitemap — отказ.
  await seedSite();
  await fs.rm(path.join(site, "sitemap.xml"));
  result = sync();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /нет sitemap\.xml/);

  // 8. Неполная сборка — отказ.
  await fs.rm(site, {recursive:true, force:true});
  await write(site, "cars/a/index.html", "x");
  await write(site, "sitemap.xml", "<urlset/>");
  result = sync();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /сборка выглядит неполной/);

  // 9. Без настроек — понятная ошибка, а не тихий пропуск.
  result = spawnSync(process.execPath, [SCRIPT], {env:{...process.env, PRIMCOM_SITE_ROOT:site, PRIMCOM_SYNC_CONFIG:path.join(tmp, "absent.env"), SYNC_METHOD:""}, encoding:"utf8"});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /SYNC_METHOD/);

  // 10. lftp: команды строятся правильно, пароль в план не попадает.
  await seedSite();
  result = sync({SYNC_METHOD:"lftp", SYNC_HOST:"ftp.example.test", SYNC_USER:"u1", SYNC_PASSWORD:"s3cret\"pass", SYNC_PROTOCOL:"sftp", SYNC_REMOTE_ROOT:"/www/primcom.ru"}, ["--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(result.stdout, /s3cret/, "пароль не должен печататься");
  assert.match(result.stdout, /open -u "u1","\*\*\*\*\*\*\*\*" sftp:\/\/ftp\.example\.test/);
  assert.match(result.stdout, /cd "\/www\/primcom\.ru"/);
  assert.match(result.stdout, /mkdir -p -f "cars\/japan\/brand\/model-0"/);
  assert.match(result.stdout, /put -O "cars\/japan\/brand\/model-0" ".*index\.html"/);
  assert.match(result.stdout, /put -O "\." ".*sitemap\.xml"/);
  assert.ok(result.stdout.indexOf("--- lftp: sitemap ---") > result.stdout.indexOf("--- lftp: pages ---"));

  console.log("Sync-to-host test passed.");
} finally {
  await fs.rm(tmp, {recursive:true, force:true});
}
