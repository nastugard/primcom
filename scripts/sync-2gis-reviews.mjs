import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

const REVIEWS_PAGE_URL = "https://2gis.ru/vladivostok/firm/70000001110927328/tab/reviews";
const REVIEWS_API_URL =
  "https://public-api.reviews.2gis.com/2.0/branches/70000001110927328/reviews?limit=12&key=6e7e1929-4ea9-4a5d-8c05-d601860389bd";
const DATA_PATH = path.join(projectRoot, "data", "2gis-reviews.json");
const INDEX_PATH = path.join(projectRoot, "index.html");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatReviewCount(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) return `${count} отзыв`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} отзыва`;
  return `${count} отзывов`;
}

function formatRatingsCount(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) return `${count} оценка`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} оценки`;
  return `${count} оценок`;
}

function formatHumanDate(iso) {
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "Asia/Vladivostok",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function getInitials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);

  return parts.map((part) => part[0]?.toUpperCase() || "").join("") || "2Г";
}

function renderStars(rating) {
  const safeRating = Math.max(0, Math.min(5, Number(rating) || 0));
  const full = "★".repeat(safeRating);
  const empty = "☆".repeat(5 - safeRating);
  return `${full}${empty}`;
}

function normalizeText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function pickFirstUrl(...values) {
  for (const value of values) {
    const text = String(value || "").trim();
    if (text) return text;
  }
  return "";
}

function mapReviewPhoto(photo) {
  const previews = photo?.preview_urls || {};
  const thumbUrl = pickFirstUrl(previews["320x"], previews["640x"], previews.url, previews["64x64"]);
  const fullUrl = pickFirstUrl(previews["1920x"], previews.url, previews["640x"], previews["320x"]);
  if (!thumbUrl) return null;

  return {
    id: String(photo?.id || ""),
    thumbUrl,
    fullUrl: fullUrl || thumbUrl,
  };
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0",
      accept: "application/json,text/plain,*/*",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }

  return response.json();
}

async function fetchText(url) {
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0",
      accept: "text/html,application/xhtml+xml",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }

  return response.text();
}

function parseSummaryFromHtml(html) {
  const descMatch = html.match(
    /<meta name="description" content="(\d+)\s+отзыва?[^"]*?Рейтинг\s+([\d.,]+)\s+на основе\s+(\d+)\s+оцен/i,
  );

  if (!descMatch) {
    return {
      reviewsCount: 0,
      rating: null,
      ratingsCount: 0,
    };
  }

  return {
    reviewsCount: Number(descMatch[1]) || 0,
    rating: Number(descMatch[2].replace(",", ".")) || null,
    ratingsCount: Number(descMatch[3]) || 0,
  };
}

function mapReview(review) {
  const authorName = review?.user?.name || "Пользователь 2ГИС";
  const authorReviewsCount = Number(review?.user?.reviews_count) || 0;
  const text = normalizeText(review?.text);
  const avatarPreview = review?.user?.photo_preview_urls || {};
  const avatarUrl = pickFirstUrl(
    avatarPreview["64x64"],
    avatarPreview["320x"],
    avatarPreview["640x"],
    avatarPreview.url,
  );
  const photos = (Array.isArray(review?.photos) ? review.photos : [])
    .map(mapReviewPhoto)
    .filter(Boolean);

  return {
    id: String(review?.id || ""),
    authorName,
    authorInitials: getInitials(authorName),
    authorAvatarUrl: avatarUrl,
    authorReviewsCount,
    dateCreated: review?.date_created || "",
    dateLabel: formatHumanDate(review?.date_created || ""),
    rating: Number(review?.rating) || 0,
    ratingLabel: renderStars(review?.rating),
    likesCount: Number(review?.likes_count) || 0,
    isVerified: Boolean(review?.is_verified),
    text,
    photosCount: photos.length,
    photos,
    sourceUrl: REVIEWS_PAGE_URL,
  };
}

function buildReviewsSection(data) {
  const summaryParts = [];

  if (data.summary.rating !== null) {
    summaryParts.push(
      `<span class="reviews-2gis__stat">Рейтинг ${escapeHtml(data.summary.rating.toFixed(1))}</span>`,
    );
  }

  if (data.summary.ratingsCount > 0) {
    summaryParts.push(
      `<span class="reviews-2gis__stat">${escapeHtml(formatRatingsCount(data.summary.ratingsCount))}</span>`,
    );
  }

  if (data.summary.reviewsCount > 0) {
    summaryParts.push(
      `<span class="reviews-2gis__stat">${escapeHtml(formatReviewCount(data.summary.reviewsCount))}</span>`,
    );
  }

  const cardsHtml = data.reviews
    .slice(0, 6)
    .map((review) => {
      const meta = [];

      if (review.authorReviewsCount > 0) {
        meta.push(`${review.authorReviewsCount} в 2ГИС`);
      }

      if (review.likesCount > 0) {
        meta.push(`Полезно: ${review.likesCount}`);
      }

      if (review.photosCount > 0) {
        meta.push(`Фото: ${review.photosCount}`);
      }

      const avatarHtml = review.authorAvatarUrl
        ? `<img class="review-card__avatar-img" src="${escapeHtml(review.authorAvatarUrl)}" alt="${escapeHtml(review.authorName)}" loading="lazy" decoding="async" />`
        : escapeHtml(review.authorInitials);

      const photosHtml = review.photos.length
        ? `
            <div class="review-card__photos" aria-label="Фото из отзыва">
${review.photos
  .slice(0, 3)
  .map(
    (photo) => `              <a class="review-card__photo" href="${escapeHtml(photo.fullUrl)}" target="_blank" rel="noopener" aria-label="Открыть фото из отзыва">
                <img src="${escapeHtml(photo.thumbUrl)}" alt="Фото из отзыва ${escapeHtml(review.authorName)}" loading="lazy" decoding="async" />
              </a>`,
  )
  .join("\n")}
            </div>`
        : "";

      return `          <article class="review-card review-card--2gis">
            <div class="review-card__top">
              <div class="review-card__avatar" aria-hidden="true">${avatarHtml}</div>
              <div class="review-card__heading">
                <p class="review-card__source">2ГИС${review.isVerified ? " • Проверенный отзыв" : ""}</p>
                <h3 class="review-card__title">${escapeHtml(review.authorName)}</h3>
                <p class="review-card__date">${escapeHtml(review.dateLabel)}</p>
              </div>
            </div>
            <div class="review-card__rating" aria-label="Оценка ${escapeHtml(review.rating)} из 5">${escapeHtml(
              review.ratingLabel,
            )}</div>
            <p class="review-card__text">${escapeHtml(review.text)}</p>
${photosHtml}
            <div class="review-card__footer">
              <p class="review-card__meta">${escapeHtml(meta.join(" • "))}</p>
              <a class="review-card__link" href="${escapeHtml(review.sourceUrl)}" target="_blank" rel="noopener">Читать в 2ГИС</a>
            </div>
          </article>`;
    })
    .join("\n");

  return `  <div class="container">
    <div class="reviews-2gis__head">
      <div>
        <h2 class="section__title">Отзывы 2ГИС</h2>
        <p class="section__lead">Реальные отзывы клиентов о работе Примком.</p>
        <div class="reviews-2gis__summary">
${summaryParts.map((part) => `          ${part}`).join("\n")}
        </div>
      </div>
      <a class="btn btn--small latest-home__cta" href="${REVIEWS_PAGE_URL}" target="_blank" rel="noopener">
        Смотреть все отзывы
      </a>
    </div>

    <div class="reviews-2gis__list" role="list">
${cardsHtml}
    </div>
  </div>`;
}

async function writeJsonFile(data) {
  await mkdir(path.dirname(DATA_PATH), { recursive: true });
  await writeFile(DATA_PATH, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

async function updateIndexHtml(sectionHtml) {
  const indexHtml = await readFile(INDEX_PATH, "utf8");
  const sectionMarkup = `<section class="section section--reviews-2gis" id="reviews" aria-label="Отзывы 2ГИС">
  <!-- 2GIS_REVIEWS:START -->
${sectionHtml}
  <!-- 2GIS_REVIEWS:END -->
    </section>`;

  const existingMarkers = /<section class="section section--reviews-2gis" id="reviews" aria-label="Отзывы 2ГИС">[\s\S]*?<!-- 2GIS_REVIEWS:END -->\s*<\/section>/;
  const legacySection = /<section class="section" id="reviews" aria-label="Отзывы">[\s\S]*?<\/section>/;

  let nextHtml;

  if (existingMarkers.test(indexHtml)) {
    nextHtml = indexHtml.replace(existingMarkers, sectionMarkup);
  } else if (legacySection.test(indexHtml)) {
    nextHtml = indexHtml.replace(legacySection, sectionMarkup);
  } else {
    throw new Error("Reviews section not found in index.html");
  }

  if (nextHtml !== indexHtml) {
    await writeFile(INDEX_PATH, nextHtml, "utf8");
  }
}

async function main() {
  const [reviewsResponse, reviewsPageHtml] = await Promise.all([
    fetchJson(REVIEWS_API_URL),
    fetchText(REVIEWS_PAGE_URL),
  ]);

  const summary = parseSummaryFromHtml(reviewsPageHtml);
  const reviews = Array.isArray(reviewsResponse?.reviews)
    ? reviewsResponse.reviews.map(mapReview).filter((review) => review.text)
    : [];

  const payload = {
    source: {
      platform: "2ГИС",
      pageUrl: REVIEWS_PAGE_URL,
      apiUrl: REVIEWS_API_URL,
      fetchedAt: new Date().toISOString(),
    },
    summary,
    reviews,
  };

  await writeJsonFile(payload);
  await updateIndexHtml(buildReviewsSection(payload));

  console.log(
    `[2gis-reviews] synced ${reviews.length} reviews, rating ${summary.rating ?? "n/a"}, ${summary.reviewsCount} reviews total`,
  );
}

main().catch((error) => {
  console.error("[2gis-reviews] sync failed", error);
  process.exitCode = 1;
});
