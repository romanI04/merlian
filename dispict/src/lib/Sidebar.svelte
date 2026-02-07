<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Artwork } from "./api";

  const LOCAL_API_URL =
    // @ts-ignore
    (import.meta as any).env?.VITE_LOCAL_API_URL ?? "http://127.0.0.1:8008";

  const dispatch = createEventDispatcher<{ close: void }>();

  export let artwork: Artwork;
  export let query: string = "";
  export let mode: "demo" | "local" = "demo";

  $: isLocal = mode === "local";

  function formatFileSize(bytes: number): string {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(ts: number): string {
    if (!ts) return "";
    try {
      return new Date(ts * 1000).toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  /** Highlight matched tokens in OCR text. XSS-safe: we escape then insert <mark> tags. */
  function highlightOcr(text: string, tokens: string[]): string {
    if (!text || !tokens?.length) return escapeHtml(text || "");
    let escaped = escapeHtml(text);
    for (const token of tokens) {
      if (!token) continue;
      const escapedToken = escapeHtml(token);
      const re = new RegExp(`(${escapedToken.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
      escaped = escaped.replace(re, "<mark>$1</mark>");
    }
    return escaped;
  }

  function escapeHtml(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /** Get a human-friendly category from the file path */
  function getCategory(path: string): string {
    const parts = path.split("/");
    const folder = parts.length > 1 ? parts[parts.length - 2] : "";
    const categoryMap: Record<string, string> = {
      errors: "Error Page",
      terminal: "Terminal Output",
      receipts: "Receipt",
      dashboards: "Dashboard",
      messaging: "Chat / Messaging",
      settings: "Settings",
      confirmations: "Confirmation",
      code: "Code Editor",
    };
    return categoryMap[folder] || folder || "Screenshot";
  }

  // Extract tokens from query for highlighting
  $: queryTokens = query
    ? query.toLowerCase().split(/[^a-zA-Z0-9]+/).filter((t) => t.length >= 2)
    : (artwork.matched_tokens ?? []);
</script>

<div class={isLocal ? "sidebar-local p-6" : "sidebar-demo p-6"}>
  <div class="flex justify-end mb-4">
    <button
      on:click={() => dispatch("close")}
      class="close-btn p-1.5 rounded-lg transition-colors"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><line x1="18" y1="6" x2="6" y2="18" /><line
          x1="6"
          y1="6"
          x2="18"
          y2="18"
        /></svg
      >
    </button>
  </div>

  <!-- Title and category -->
  <div class="mb-6">
    <div class="category-badge inline-block px-2 py-0.5 rounded-md text-[11px] font-medium uppercase tracking-wide mb-2">
      {isLocal ? "Screenshot" : getCategory(artwork.url || artwork.objectnumber || "")}
    </div>
    <h2 class="text-xl font-semibold leading-tight mb-1">{artwork.title}</h2>

    {#if isLocal}
      <!-- Local mode: Open/Reveal actions -->
      <div class="flex gap-2 mt-4">
        <button
          class="action-btn-primary px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          on:click={async () => {
            const base = (LOCAL_API_URL.endsWith("/")
              ? LOCAL_API_URL.slice(0, -1)
              : LOCAL_API_URL);
            await fetch(base + "/open", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ path: artwork.url, reveal: false }),
            });
          }}
        >
          Open
        </button>
        <button
          class="action-btn-secondary px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          on:click={async () => {
            const base = (LOCAL_API_URL.endsWith("/")
              ? LOCAL_API_URL.slice(0, -1)
              : LOCAL_API_URL);
            await fetch(base + "/open", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({ path: artwork.url, reveal: true }),
            });
          }}
        >
          Reveal in Finder
        </button>
      </div>
    {/if}
  </div>

  <!-- Metadata -->
  <dl class="metadata">
    {#if artwork.dimensions}
      <dt>Dimensions</dt>
      <dd>{artwork.dimensions}</dd>
    {/if}

    {#if isLocal && artwork.created_at}
      <dt>Created</dt>
      <dd>{formatDate(artwork.created_at)}</dd>
    {/if}

    {#if isLocal && artwork.file_size}
      <dt>File size</dt>
      <dd>{formatFileSize(artwork.file_size)}</dd>
    {/if}

    {#if isLocal && artwork.folder}
      <dt>Folder</dt>
      <dd class="break-all text-xs opacity-70">{artwork.folder}</dd>
    {/if}

    {#if artwork.ocr_word_count}
      <dt>Text detected</dt>
      <dd>{artwork.ocr_word_count} words</dd>
    {/if}
  </dl>

  <!-- OCR evidence -->
  {#if artwork.description}
    <div class="mt-6 pt-6 border-t {isLocal ? 'border-stone-700' : 'border-neutral-200'}">
      <div class="text-[11px] font-semibold uppercase tracking-wide mb-2 {isLocal ? 'text-stone-400' : 'text-neutral-400'}">
        {queryTokens.length > 0 ? "Matched text" : "Detected text"}
      </div>
      <div class="ocr-preview text-sm leading-relaxed {isLocal ? 'text-stone-300' : 'text-neutral-600'}">
        {@html highlightOcr(artwork.description, queryTokens)}
      </div>
    </div>
  {/if}

  <!-- File path (local only) -->
  {#if isLocal && artwork.url}
    <div class="mt-6 pt-4 border-t {isLocal ? 'border-stone-700' : 'border-neutral-200'}">
      <div class="text-[11px] font-semibold uppercase tracking-wide mb-1 {isLocal ? 'text-stone-500' : 'text-neutral-400'}">Path</div>
      <div class="text-xs break-all {isLocal ? 'text-stone-500' : 'text-neutral-400'}">{artwork.url}</div>
    </div>
  {/if}

  <!-- Demo footer -->
  {#if !isLocal}
    <div class="mt-8 pt-6 border-t border-neutral-200">
      <p class="text-xs text-neutral-400 leading-relaxed">
        This is a curated demo with synthetic screenshots. <a href="#/local" class="underline underline-offset-2 hover:text-neutral-600">Search your own library</a> to try it with your real files.
      </p>
    </div>
  {/if}
</div>

<style lang="postcss">
  .sidebar-local {
    @apply bg-stone-900 text-stone-100;
  }

  .sidebar-demo {
    @apply text-neutral-900;
  }

  .sidebar-local .close-btn {
    @apply text-stone-400 hover:bg-stone-700 hover:text-stone-200;
  }

  .sidebar-demo .close-btn {
    @apply text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700;
  }

  .sidebar-local .category-badge {
    @apply bg-stone-800 text-stone-400;
  }

  .sidebar-demo .category-badge {
    @apply bg-neutral-100 text-neutral-500;
  }

  .action-btn-primary {
    @apply bg-white text-stone-900 hover:bg-stone-200;
  }

  .action-btn-secondary {
    @apply bg-stone-800 text-stone-200 hover:bg-stone-700 border border-stone-600;
  }

  .metadata dt {
    @apply text-[11px] font-semibold uppercase tracking-wide mt-3 first:mt-0;
  }

  .sidebar-local .metadata dt {
    color: theme(colors.stone.500);
  }

  .sidebar-demo .metadata dt {
    @apply text-neutral-400;
  }

  .metadata dd {
    @apply text-sm mt-0.5;
  }

  .sidebar-local .metadata dd {
    color: theme(colors.stone.200);
  }

  .sidebar-demo .metadata dd {
    @apply text-neutral-700;
  }

  .ocr-preview :global(mark) {
    background-color: theme(colors.amber.400 / 40%);
    color: inherit;
    padding: 1px 3px;
    border-radius: 3px;
  }
</style>
