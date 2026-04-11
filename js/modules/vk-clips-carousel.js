const DESKTOP_BREAKPOINT = "(min-width: 861px)";

function getScrollStep(grid) {
  const firstCard = grid.querySelector(".info-card--vk");

  if (!firstCard) {
    return Math.max(grid.clientWidth * 0.9, 280);
  }

  const styles = window.getComputedStyle(grid);
  const gap = Number.parseFloat(styles.columnGap || styles.gap || "0") || 0;

  return firstCard.getBoundingClientRect().width + gap;
}

function updateButtons(grid, prevButton, nextButton, isDesktop) {
  const buttonsEnabled = isDesktop && grid.scrollWidth > grid.clientWidth + 8;
  const maxScrollLeft = Math.max(0, grid.scrollWidth - grid.clientWidth);
  const atStart = grid.scrollLeft <= 4;
  const atEnd = grid.scrollLeft >= maxScrollLeft - 4;

  prevButton.disabled = !buttonsEnabled || atStart;
  nextButton.disabled = !buttonsEnabled || atEnd;
}

export function initVkClipsCarousel() {
  const grid = document.querySelector("[data-vk-clips-grid]");
  const prevButton = document.querySelector("[data-vk-clips-prev]");
  const nextButton = document.querySelector("[data-vk-clips-next]");

  if (!grid || !prevButton || !nextButton) {
    return;
  }

  const desktopMedia = window.matchMedia(DESKTOP_BREAKPOINT);

  const sync = () => {
    updateButtons(grid, prevButton, nextButton, desktopMedia.matches);
  };

  const handleArrowClick = (direction) => {
    if (!desktopMedia.matches) {
      return;
    }

    grid.scrollBy({
      left: getScrollStep(grid) * direction,
      behavior: "smooth",
    });
  };

  prevButton.addEventListener("click", () => handleArrowClick(-1));
  nextButton.addEventListener("click", () => handleArrowClick(1));
  grid.addEventListener("scroll", sync, { passive: true });
  window.addEventListener("resize", sync, { passive: true });

  if (typeof desktopMedia.addEventListener === "function") {
    desktopMedia.addEventListener("change", sync);
  } else if (typeof desktopMedia.addListener === "function") {
    desktopMedia.addListener(sync);
  }

  sync();
}
