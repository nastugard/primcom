export function initHeader() {
  const header = document.querySelector("[data-header]");
  if (!header) return;

  const root = document.documentElement;
  const setHeaderOffset = () => {
    const h = header.getBoundingClientRect().height;
    root.style.setProperty("--header-offset", `${Math.ceil(h + 12)}px`);
  };

  setHeaderOffset();
  window.addEventListener("resize", setHeaderOffset, { passive: true });
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(setHeaderOffset).observe(header);
  }

  const nav = document.querySelector("[data-nav]");
  if (!nav) return;

  const indicator = nav.querySelector("[data-nav-indicator]");
  const burger = header.querySelector("[data-burger]");
  const mobile = window.matchMedia("(max-width: 860px)");

  const dropdowns = Array.from(nav.querySelectorAll("details.nav-dd"));
  const closeAll = (except) => {
    dropdowns.forEach((dd) => {
      if (except && dd === except) return;
      dd.removeAttribute("open");
    });
  };

  const setMenuOpen = (open, returnFocus = false) => {
    const expanded = !!open && mobile.matches;
    header.classList.toggle("is-menu-open", expanded);
    burger?.setAttribute("aria-expanded", String(expanded));
    burger?.setAttribute("aria-label", expanded ? "Закрыть меню" : "Открыть меню");
    if (expanded) nav.scrollTop = 0;
    if (!expanded) closeAll();
    if (returnFocus && mobile.matches) burger?.focus({ preventScroll: true });
  };

  if (burger) {
    burger.hidden = false;
    header.classList.add("has-mobile-menu");
    burger.addEventListener("click", () => {
      const open = !header.classList.contains("is-menu-open");
      setMenuOpen(open);
      if (open) nav.querySelector("summary, a[href]")?.focus({ preventScroll: true });
    });
    const resetMenu = () => {
      const focusWasInNav = nav.contains(document.activeElement);
      setMenuOpen(false, focusWasInNav);
      setHeaderOffset();
    };
    if (mobile.addEventListener) mobile.addEventListener("change", resetMenu);
    else mobile.addListener(resetMenu);
  }

  if (dropdowns.length) {

    dropdowns.forEach((dd) => {
      dd.addEventListener("toggle", () => {
        if (dd.open) closeAll(dd);
      });
    });

    document.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Node)) return;
      if (header.contains(target)) return;
      const restoreFocus = header.classList.contains("is-menu-open") &&
        (nav.contains(document.activeElement) || document.activeElement === document.body);
      closeAll();
      setMenuOpen(false, restoreFocus);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const expandedDropdown = dropdowns.find((dd) => dd.open);
      if (expandedDropdown) {
        closeAll();
        expandedDropdown.querySelector("summary")?.focus({ preventScroll: true });
      } else if (header.classList.contains("is-menu-open")) {
        setMenuOpen(false, true);
      } else return;
      e.preventDefault();
    });

    nav.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      const link = target.closest("a[href]");
      if (!link) return;
      closeAll();
      setMenuOpen(false);
    });
  }

  // Навигация не модальная: при уходе фокуса за пределы шапки она сворачивается.
  header.addEventListener("focusout", () => {
    window.requestAnimationFrame(() => {
      if (!header.contains(document.activeElement)) {
        setMenuOpen(false, header.classList.contains("is-menu-open") && document.activeElement === document.body);
      }
    });
  });

  const links = Array.from(nav.querySelectorAll("a[href]"));

  const hashLinks = links.filter((l) => (l.getAttribute("href") || "").includes("#"));

  const canSmooth = !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  const scrollToId = (id) => {
    const target = document.getElementById(id);
    if (!target) return;

    const headerH = header.getBoundingClientRect().height + 12;

    if (window.__smoother && typeof window.__smoother.scrollTo === "function") {
      const y = typeof window.__smoother.offset === "function" ? window.__smoother.offset(target, "top top") : null;
      const top = typeof y === "number" ? Math.max(0, y - headerH) : Math.max(0, window.scrollY + target.getBoundingClientRect().top - headerH);
      window.__smoother.scrollTo(top, canSmooth);
      window.history.pushState(null, "", `#${id}`);
      return;
    }

    const top = Math.max(0, window.scrollY + target.getBoundingClientRect().top - headerH);
    window.scrollTo({ top, behavior: canSmooth ? "smooth" : "auto" });
    window.history.pushState(null, "", `#${id}`);
  };

  const getIdFromHref = (href) => {
    const idx = href.indexOf("#");
    if (idx === -1) return null;
    return href.slice(idx + 1);
  };

  const normalizePathname = (pathname) => {
    if (!pathname) return "/";
    let p = pathname;
    if (p.endsWith("/index.html")) p = p.slice(0, -"/index.html".length + 1);
    if (p === "/index.html") p = "/";
    if (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
    return p;
  };

  const getLinkUrl = (link) => {
    const href = link.getAttribute("href") || "";
    try {
      return new URL(href, window.location.href);
    } catch {
      return null;
    }
  };

  const getInitialActiveLink = () => {
    const currentPath = normalizePathname(window.location.pathname);
    const currentHash = window.location.hash || "";

    if (currentHash && hashLinks.length) {
      const byHash = hashLinks.find((l) => {
        const u = getLinkUrl(l);
        if (!u) return false;
        return normalizePathname(u.pathname) === currentPath && u.hash === currentHash;
      });
      if (byHash) return byHash;
    }

    const byPath = links.find((l) => {
      const u = getLinkUrl(l);
      if (!u) return false;
      return normalizePathname(u.pathname) === currentPath && !u.hash;
    });

    return byPath || null;
  };

  const setActiveClass = (activeLink) => {
    if (!activeLink) return;
    links.forEach((l) => l.classList.toggle("is-active", l === activeLink));
  };

  const markActiveDropdownSummary = () => {
    if (!dropdowns.length) return;
    const currentPath = normalizePathname(window.location.pathname);

    dropdowns.forEach((dd) => {
      const summary = dd.querySelector("summary");
      if (!summary) return;
      const ddLinks = Array.from(dd.querySelectorAll("a[href]"));
      const isActive = ddLinks.some((l) => {
        const u = getLinkUrl(l);
        if (!u) return false;
        return normalizePathname(u.pathname) === currentPath;
      });
      summary.classList.toggle("is-active", isActive);
    });
  };

  // Подсветка активного пункта для dropdown делается всегда.
  markActiveDropdownSummary();

  // GSAP может быть недоступен, если CDN не загрузился.
  // В этом случае сайт остаётся функциональным без анимаций.
  if (!window.gsap || !window.ScrollTrigger) {
    const onScroll = () => {
      const active = window.scrollY > 10;
      header.classList.toggle("is-detached", active);
      window.requestAnimationFrame(setHeaderOffset);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return;
  }

  const { gsap } = window;
  gsap.registerPlugin(window.ScrollTrigger);

  // При прокрутке добавляем класс (визуально сейчас нейтрально, но может пригодиться дальше).
  window.ScrollTrigger.create({
    start: 10,
    end: 99999,
    onToggle: (self) => {
      header.classList.toggle("is-detached", self.isActive);
      window.requestAnimationFrame(setHeaderOffset);
    },
  });

  hashLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      const href = link.getAttribute("href") || "";
      const id = getIdFromHref(href);
      if (!id) return;
      const section = document.getElementById(id);
      if (!section) return;
      e.preventDefault();
      scrollToId(id);
    });
  });

  const state = { activeLink: null };

  const moveIndicatorToLink = (link, immediate) => {
    const navRect = nav.getBoundingClientRect();
    const linkRect = link.getBoundingClientRect();
    const left = linkRect.left - navRect.left;

    const w = Math.max(18, linkRect.width * 0.70);
    const x = left + (linkRect.width - w) / 2;

    if (immediate) {
      gsap.set(indicator, { x, width: w });
      return;
    }

    gsap.to(indicator, { x, width: w, duration: 0.35, ease: "power3.out" });
  };

  const setActive = (link) => {
    if (!link) return;
    state.activeLink = link;
    setActiveClass(link);
    if (indicator) moveIndicatorToLink(link);
  };

  const initialActive = getInitialActiveLink();
  if (initialActive) {
    state.activeLink = initialActive;
    setActiveClass(initialActive);
    if (indicator) {
      moveIndicatorToLink(initialActive, true);
    }
  }

  if (!indicator) return;

  // Init позиционирования.
  if (!initialActive) {
    indicator.style.opacity = "0";
  }

  const onResize = () => {
    if (!state.activeLink) return;
    indicator.style.opacity = "";
    moveIndicatorToLink(state.activeLink, true);
  };

  window.addEventListener("resize", onResize, { passive: true });

  // Hover-подсказка.
  links.forEach((link) => {
    link.addEventListener("mouseenter", () => moveIndicatorToLink(link));
    link.addEventListener("mouseleave", () => {
      if (state.activeLink) moveIndicatorToLink(state.activeLink);
    });
  });

  // Авто-активация по скроллу.
  hashLinks.forEach((link) => {
    const href = link.getAttribute("href") || "";
    const id = getIdFromHref(href);
    if (!id) return;
    const section = document.getElementById(id);
    if (!section) return;

    window.ScrollTrigger.create({
      trigger: section,
      start: "top 55%",
      end: "bottom 45%",
      onEnter: () => setActive(link),
      onEnterBack: () => setActive(link),
    });
  });
}
