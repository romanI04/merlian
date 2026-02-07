// See main.py for the source of this type.

export type SearchMode = "demo" | "local";

export type Artwork = {
  id: number;
  objectnumber: string;
  url: string;
  image_url: string;

  dimensions: string;
  dimheight: number;
  dimwidth: number;

  title: string | null;
  description: string | null;
  labeltext: string | null;
  people: string[];
  dated: string;
  datebegin: number;
  dateend: number;
  century: string | null;

  department: string;
  division: string | null;
  culture: string | null;
  classification: string;
  technique: string | null;
  medium: string | null;

  accessionyear: number | null;
  verificationlevel: number;
  totaluniquepageviews: number;
  totalpageviews: number;

  copyright: string | null;
  creditline: string;

  // Merlian local-mode extensions
  matched_tokens?: string[];
  file_size?: number;
  created_at?: number;
  folder?: string;
  ocr_word_count?: number;
};

export type SearchResult = {
  score: number;
  artwork: Artwork;
};

const DEMO_API_URL =
  import.meta.env.VITE_DEMO_API_URL ??
  "https://ekzhang--dispict-suggestions.modal.run/";

const LOCAL_API_URL =
  import.meta.env.VITE_LOCAL_API_URL ??
  "http://127.0.0.1:8008";

let SEARCH_MODE: SearchMode = (window.location.hash || "").includes("local")
  ? "local"
  : "demo";

export function setSearchMode(mode: SearchMode) {
  SEARCH_MODE = mode;
}

function baseUrl(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function localBase(): string {
  return baseUrl(LOCAL_API_URL);
}

function demoBase(): string {
  return baseUrl(DEMO_API_URL);
}

/** Queries the backend API for results matching a text phrase. */
export async function loadSuggestions(
  text: string,
  n?: number,
  signal?: AbortSignal
): Promise<SearchResult[]> {
  // Local-first API (Merlian engine)
  if (SEARCH_MODE === "local") {
    const resp = await fetch(localBase() + "/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: text, k: n ?? 64, mode: "hybrid" }),
      signal,
    });

    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      console.error("Merlian local /search failed", resp.status, errText);
      throw new Error(`Local search failed: ${resp.status}`);
    }

    const data = await resp.json();
    const results = (data?.results ?? []) as Array<any>;

    const total = results.length || 1;
    return results.map((r, i) => {
      const w = r.width ?? 1200;
      const h = r.height ?? 800;
      const path = r.path as string;
      const filename = path.split("/").slice(-1)[0] ?? path;
      const ocrText = (r.ocr_preview as string) || "";
      const ocrWordCount = ocrText.trim() ? ocrText.trim().split(/\s+/).length : 0;
      // Scale top results larger, tail results smaller (creates size variation for tight packing)
      const rankScale = 1.3 - 0.7 * (i / total);

      const artwork: Artwork = {
        id: i,
        objectnumber: filename,
        url: path, // local path; Sidebar handles open/reveal
        image_url:
          localBase() +
          (r.thumb_url
            ? r.thumb_url.startsWith("/")
              ? r.thumb_url
              : "/" + r.thumb_url
            : ""),

        dimensions: `${w}×${h}px`,
        dimheight: (h / 55) * rankScale,
        dimwidth: (w / 55) * rankScale,

        title: filename,
        description: ocrText || null,
        labeltext: null,
        people: [],
        dated: r.created_at ? new Date(r.created_at * 1000).toLocaleDateString() : "",
        datebegin: 0,
        dateend: 0,
        century: null,

        department: "",
        division: null,
        culture: null,
        classification: "Screenshot",
        technique: null,
        medium: null,

        accessionyear: null,
        verificationlevel: 0,
        totaluniquepageviews: 0,
        totalpageviews: 0,

        copyright: null,
        creditline: "",

        // Merlian extensions
        matched_tokens: r.matched_tokens ?? [],
        file_size: r.file_size ?? 0,
        created_at: r.created_at ?? 0,
        folder: r.folder ?? "",
        ocr_word_count: ocrWordCount,
      };

      return { score: r.score ?? 0, artwork };
    });
  }

  // Demo mode — use local engine's demo-search endpoint (pre-computed demo dataset)
  const demoApiBase = localBase();
  const resp = await fetch(demoApiBase + "/demo-search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query: text, k: n ?? 64, mode: "hybrid" }),
    signal,
  });

  if (!resp.ok) {
    // Fallback: try upstream Dispict demo API
    let url = demoBase() + "?text=" + encodeURIComponent(text);
    if (n) url += "&n=" + n;
    const fallbackResp = await fetch(url, { signal });
    return await fallbackResp.json();
  }

  const data = await resp.json();
  const results = (data?.results ?? []) as Array<any>;
  const demoTotal = results.length || 1;

  return results.map((r: any, i: number) => {
    const w = r.width ?? 1440;
    const h = r.height ?? 900;
    const path = r.path as string;
    const filename = path.split("/").slice(-1)[0] ?? path;
    const ocrText = (r.ocr_preview as string) || "";
    const ocrWordCount = ocrText.trim() ? ocrText.trim().split(/\s+/).length : 0;
    // Scale top results larger, tail results smaller (creates size variation for tight packing)
    const rankScale = 1.3 - 0.7 * (i / demoTotal);

    const artwork: Artwork = {
      id: i,
      objectnumber: filename,
      url: path,
      image_url:
        demoApiBase +
        (r.thumb_url
          ? r.thumb_url.startsWith("/")
            ? r.thumb_url
            : "/" + r.thumb_url
          : ""),

      dimensions: `${w}×${h}px`,
      dimheight: (h / 55) * rankScale,
      dimwidth: (w / 55) * rankScale,

      title: filename,
      description: ocrText || null,
      labeltext: null,
      people: [],
      dated: r.created_at ? new Date(r.created_at * 1000).toLocaleDateString() : "",
      datebegin: 0,
      dateend: 0,
      century: null,

      department: "",
      division: null,
      culture: null,
      classification: "Screenshot",
      technique: null,
      medium: null,

      accessionyear: null,
      verificationlevel: 0,
      totaluniquepageviews: 0,
      totalpageviews: 0,

      copyright: null,
      creditline: "",

      matched_tokens: r.matched_tokens ?? [],
      file_size: r.file_size ?? 0,
      created_at: r.created_at ?? 0,
      folder: r.folder ?? "",
      ocr_word_count: ocrWordCount,
    };

    return { score: r.score ?? 0, artwork };
  });
}
