const EMBED_HOSTS = new Set(["vk.com", "www.vk.com", "vkvideo.ru", "www.vkvideo.ru"]);

function normalizeAbsoluteUrl(value) {
  if (!value) return "";

  try {
    return new URL(value, window.location.href).toString();
  } catch {
    return "";
  }
}

function isValidClipLink(value) {
  if (!value) return false;

  try {
    const url = new URL(value);
    if (!/^https?:$/.test(url.protocol)) return false;
    return EMBED_HOSTS.has(url.hostname.toLowerCase());
  } catch {
    return false;
  }
}

function isValidEmbedUrl(value) {
  if (!value) return false;

  try {
    const url = new URL(value);
    if (!/^https?:$/.test(url.protocol)) return false;
    if (!EMBED_HOSTS.has(url.hostname.toLowerCase())) return false;
    return url.pathname.endsWith("/video_ext.php");
  } catch {
    return false;
  }
}

function createEmbedFrame(src, title) {
  const frame = document.createElement("iframe");
  frame.className = "vk-video__frame";
  frame.src = src;
  frame.title = title;
  frame.loading = "lazy";
  frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
  frame.referrerPolicy = "strict-origin-when-cross-origin";
  frame.allowFullscreen = true;
  return frame;
}

export function initVkClips() {
  const root = document.querySelector("[data-vk-clips]");
  if (!root) return;

  const cards = Array.from(root.querySelectorAll("[data-vk-clip-card]"));
  if (!cards.length) {
    root.hidden = true;
    return;
  }

  let visibleCards = 0;

  cards.forEach((card) => {
    const player = card.querySelector("[data-vk-clip-player]");
    const loadBtn = card.querySelector("[data-vk-clip-load]");
    const link = card.querySelector("[data-vk-clip-link]");
    const title = (card.querySelector(".info-card__title")?.textContent || "VK Клип").trim();

    if (!player || !link) {
      card.hidden = true;
      return;
    }

    const clipLink = normalizeAbsoluteUrl(link.getAttribute("href"));
    const embedUrl = normalizeAbsoluteUrl(player.getAttribute("data-vk-clip-embed"));

    if (!isValidClipLink(clipLink)) {
      card.hidden = true;
      return;
    }

    link.href = clipLink;
    visibleCards += 1;

    if (!loadBtn || !isValidEmbedUrl(embedUrl)) {
      if (loadBtn) loadBtn.hidden = true;
      return;
    }

    loadBtn.hidden = false;

    loadBtn.addEventListener(
      "click",
      () => {
        if (player.dataset.state === "loaded") return;

        player.replaceChildren(createEmbedFrame(embedUrl, title));
        player.dataset.state = "loaded";
        player.classList.add("is-loaded");
      },
      { once: true }
    );
  });

  root.hidden = visibleCards === 0;
}
