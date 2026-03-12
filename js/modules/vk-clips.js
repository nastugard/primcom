const ALLOWED_EMBED_HOSTS = new Set(["vkvideo.ru", "www.vkvideo.ru", "vk.com", "www.vk.com"]);

function getSafeEmbedUrl(rawUrl) {
  if (!rawUrl) return null;

  try {
    const url = new URL(rawUrl, window.location.origin);
    const isAllowedPath = url.pathname === "/video_ext.php";

    if (!ALLOWED_EMBED_HOSTS.has(url.hostname) || !isAllowedPath) {
      return null;
    }

    return url;
  } catch {
    return null;
  }
}

function buildAutoplayUrl(url) {
  const nextUrl = new URL(url.toString());
  nextUrl.searchParams.set("autoplay", "1");
  return nextUrl.toString();
}

function createFrame(src, title) {
  const frame = document.createElement("iframe");
  frame.className = "vk-video__frame";
  frame.src = src;
  frame.title = title || "VK клип";
  frame.loading = "lazy";
  frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
  frame.referrerPolicy = "strict-origin-when-cross-origin";
  frame.allowFullscreen = true;
  return frame;
}

function loadClip(player, trigger) {
  if (!player || player.classList.contains("is-loaded")) {
    return;
  }

  const safeEmbedUrl = getSafeEmbedUrl(trigger.dataset.vkClipEmbed);

  if (!safeEmbedUrl) {
    return;
  }

  const title = trigger.dataset.vkClipTitle || trigger.getAttribute("aria-label") || "VK клип";
  const frame = createFrame(buildAutoplayUrl(safeEmbedUrl), title);

  player.append(frame);
  player.classList.add("is-loaded");
}

export function initVkClips() {
  const root = document.querySelector("[data-vk-clips]");

  if (!root) {
    return;
  }

  root.querySelectorAll("[data-vk-clip-load]").forEach((trigger) => {
    const player = trigger.closest("[data-vk-clip-player]");
    const safeEmbedUrl = getSafeEmbedUrl(trigger.dataset.vkClipEmbed);

    if (!player || !safeEmbedUrl) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      loadClip(player, trigger);
    });
  });
}
