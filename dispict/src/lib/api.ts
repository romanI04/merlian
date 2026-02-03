// See main.py for the source of this type.
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
};

export type SearchResult = {
  score: number;
  artwork: Artwork;
};

const API_URL =
  import.meta.env.VITE_APP_API_URL ??
  "https://ekzhang--dispict-suggestions.modal.run/";

function baseUrl(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function isLocalApi(url: string): boolean {
  return baseUrl(url).includes("127.0.0.1:8008") || baseUrl(url).includes("localhost:8008");
}

/** Queries the backend API for results matching a text phrase. */
export async function loadSuggestions(
  text: string,
  n?: number,
  signal?: AbortSignal
): Promise<SearchResult[]> {
  // Local-first API (Merlian engine)
  if (isLocalApi(API_URL)) {
    const resp = await fetch(baseUrl(API_URL) + "/search", {
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

    return results.map((r, i) => {
      const w = r.width ?? 1200;
      const h = r.height ?? 800;
      const path = r.path as string;
      const filename = path.split("/").slice(-1)[0] ?? path;

      const artwork: Artwork = {
        id: i,
        objectnumber: filename,
        url: path, // local path; Sidebar handles open/reveal
        image_url:
          baseUrl(API_URL) +
          (r.thumb_url ? (r.thumb_url.startsWith("/") ? r.thumb_url : "/" + r.thumb_url) : ""),

        dimensions: `${w}×${h}px`,
        dimheight: h / 200,
        dimwidth: w / 200,

        title: filename,
        description: null,
        labeltext: null,
        people: [],
        dated: "",
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
      };

      return { score: r.score ?? 0, artwork };
    });
  }

  // Upstream Dispict demo API
  let url = baseUrl(API_URL) + "?text=" + encodeURIComponent(text);
  if (n) url += "&n=" + n;
  const resp = await fetch(url, { signal });
  return await resp.json();
}
