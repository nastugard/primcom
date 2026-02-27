function getRoot() {
  return document.documentElement.dataset.root || "./";
}

function normalizeRoot(root) {
  if (!root.endsWith("/")) return `${root}/`;
  return root;
}

const FOOTER_FALLBACK_HTML = `
<footer class="site-footer" data-footer>
  <div class="container site-footer__inner">
    <div class="footer-col">
      <h2 class="footer-title">Контакты</h2>
      <p class="footer-text">Телефон: <a href="tel:+79532222275">+7 (953) 222-22-75</a></p>
      <p class="footer-text">Email: <a href="mailto:info@primcom.ru">info@primcom.ru</a></p>
      <p class="footer-text">Владивосток, проспект Острякова 13, офис 317</p>
    </div>

    <div class="footer-col">
      <h2 class="footer-title">Основной сайт</h2>
      <p class="footer-text"><a href="https://primcom.ru/" rel="noopener" target="_blank">primcom.ru</a></p>
      <p class="footer-text"><a href="https://primcom.ru/pages/auto-iz-yaponii.html" rel="noopener" target="_blank">Авто из Японии</a></p>
      <p class="footer-text"><a href="https://primcom.ru/pages/auto-iz-korei.html" rel="noopener" target="_blank">Авто из Кореи</a></p>
      <p class="footer-text"><a href="https://primcom.ru/pages/auto-iz-kitaya.html" rel="noopener" target="_blank">Авто из Китая</a></p>
      <p class="footer-text"><a href="./pages/kontakty.html">Контакты на примком.рф</a></p>
    </div>
  </div>

  <div class="container footer-bottom">
    <p class="footer-copy">© <span data-year></span> Примком. Все права защищены.</p>
  </div>
</footer>
`.trim();

function setLogoSrc(root) {
  const logo = document.querySelector("[data-logo]");
  if (!logo) return;

  const src = logo.getAttribute("data-src-light") || "";
  if (!src) return;

  logo.src = normalizeRoot(root) + src;
}

function fixLinksRoot(root) {
  const anchors = document.querySelectorAll("a[href^='./']");
  anchors.forEach((a) => {
    const href = a.getAttribute("href");
    if (!href) return;

    const normalized = normalizeRoot(root) + href.replace(/^\.\//, "");
    a.setAttribute("href", normalized);
  });
}

async function inject(selector, url) {
  const target = document.querySelector(selector);
  if (!target) return;

  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Не удалось загрузить компонент: ${url}`);
    target.innerHTML = await res.text();
    return;
  } catch (err) {
    try {
      const u = new URL(url, window.location.href);
      const alt = `${u.origin}/${u.pathname.replace(/^\/+/, "").replace(/^(?:\.\.\/)+/, "")}`;
      const res2 = await fetch(alt, { cache: "no-store" });
      if (!res2.ok) throw new Error(`Не удалось загрузить компонент: ${alt}`);
      target.innerHTML = await res2.text();
      return;
    } catch (err2) {
      console.error(err2);
    }
    console.error(err);

    if (selector === "#site-footer") {
      target.innerHTML = FOOTER_FALLBACK_HTML;
    }
  }
}

export async function loadSharedComponents() {
  const root = getRoot();

  await Promise.all([
    inject("#site-header", normalizeRoot(root) + "components/header.html"),
    inject("#site-footer", normalizeRoot(root) + "components/footer.html"),
  ]);

  const footerTarget = document.querySelector("#site-footer");
  if (footerTarget && footerTarget.innerHTML.trim() === "") {
    footerTarget.innerHTML = FOOTER_FALLBACK_HTML;
  }

  setLogoSrc(root);
  fixLinksRoot(root);

  const yearEl = document.querySelector("[data-year]");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
}
