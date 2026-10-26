// Вкладки «Свежая подборка авто» на главной.
// Панели — те же блоки [data-latest-home], их по-прежнему заполняет latest-cars-home.js;
// здесь только переключение видимости, клавиатура и выбор вкладки по #якорю.

const FINAL_EMPTY_STATUS = /^(Пока нет|Нет подходящих|Не удалось|Секция недоступна)/;

function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

export function initLatestTabs() {
  qsa("[data-latest-tabs]").forEach((root) => {
    const tabs = qsa('[role="tab"]', root);
    const panelOf = (tab) => document.getElementById(tab.getAttribute("aria-controls"));
    if (!tabs.length || tabs.some((tab) => !panelOf(tab))) return;

    let userPicked = false;

    const select = (tab, { focus = false } = {}) => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        panelOf(t).hidden = !on;
      });
      if (focus) tab.focus();
    };

    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => {
        userPicked = true;
        select(tab);
      });
      tab.addEventListener("keydown", (e) => {
        const last = tabs.length - 1;
        const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: last }[e.key];
        if (next === undefined) return;
        e.preventDefault();
        userPicked = true;
        select(tabs[(next + tabs.length) % tabs.length], { focus: true });
      });
    });

    // Старые ссылки вида #latest-korea-home открывают нужную вкладку.
    const fromHash = () => {
      const tab = tabs.find((t) => `#${t.getAttribute("aria-controls")}` === window.location.hash);
      if (!tab) return;
      userPicked = true;
      select(tab);
      root.scrollIntoView({ block: "start" });
    };
    window.addEventListener("hashchange", fromHash);
    fromHash();

    // Если в выбранной по умолчанию стране объявлений нет, показываем первую страну с машинами,
    // пока посетитель сам не переключил вкладку.
    const listOf = (tab) => panelOf(tab).querySelector("[data-latest-home-list]");
    const statusOf = (tab) => panelOf(tab).querySelector("[data-latest-home-status]");
    const fallback = () => {
      if (userPicked) return;
      const active = tabs.find((t) => t.getAttribute("aria-selected") === "true");
      const status = (statusOf(active)?.textContent || "").trim();
      if (listOf(active)?.children.length || !FINAL_EMPTY_STATUS.test(status)) return;
      const filled = tabs.find((t) => listOf(t)?.children.length);
      if (filled) select(filled);
    };
    const observer = new MutationObserver(fallback);
    tabs.forEach((tab) => {
      const list = listOf(tab);
      const status = statusOf(tab);
      if (list) observer.observe(list, { childList: true });
      if (status) observer.observe(status, { childList: true, characterData: true, subtree: true });
    });
  });
}
