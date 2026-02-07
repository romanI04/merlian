<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Artwork } from "./api";

  const LOCAL_API_URL =
    // @ts-ignore
    (import.meta as any).env?.VITE_LOCAL_API_URL ?? "http://127.0.0.1:8008";

  const dispatch = createEventDispatcher<{ close: void }>();

  export let artwork: Artwork;
  export let query: string = "";

  $: isLocal = Boolean(artwork?.url?.startsWith("/") && !artwork?.url?.startsWith("http"));

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

  // Extract tokens from query for highlighting
  $: queryTokens = query
    ? query.toLowerCase().split(/[^a-zA-Z0-9]+/).filter((t) => t.length >= 2)
    : (artwork.matched_tokens ?? []);
</script>

<div class={isLocal ? "bg-stone-900 text-stone-100 p-6" : "text-neutral-900 p-6"}>
  <div class="flex justify-end mb-4">
    <button
      on:click={() => dispatch("close")}
      class={isLocal ? "p-1 rounded-md hover:bg-stone-700" : "p-1 rounded-md hover:bg-neutral-200"}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="feather feather-x"
        ><line x1="18" y1="6" x2="6" y2="18" /><line
          x1="6"
          y1="6"
          x2="18"
          y2="18"
        /></svg
      >
    </button>
  </div>

  <div class="mb-8">
    <h2 class="text-2xl fontvar-heading mb-1">{artwork.title}</h2>
    <p class={isLocal ? "text-stone-400 text-sm" : "text-neutral-500 text-sm"}>{artwork.objectnumber}</p>

    {#if isLocal}
      <div class="flex gap-2 mt-4">
        <button
          class="inline-block px-3 py-1.5 bg-white text-stone-900 hover:bg-stone-200 rounded-md"
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
          class="inline-block px-3 py-1.5 bg-stone-700 text-stone-100 hover:bg-stone-600 rounded-md border border-stone-600"
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
    {:else}
      <a
        href={artwork.url}
        target="_blank"
        rel="noopener noreferrer"
        class="inline-block px-3 py-1.5 bg-neutral-900 text-white hover:bg-neutral-700 rounded-md mt-4"
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
          class="inline -mt-1 mr-1 feather feather-external-link"
          ><path
            d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
          /><polyline points="15 3 21 3 21 9" /><line
            x1="10"
            y1="14"
            x2="21"
            y2="3"
          /></svg
        >
        View Source
      </a>
    {/if}
  </div>

  <dl>
    {#if isLocal}
      <!-- Local mode: rich metadata -->
      {#if artwork.created_at}
        <dt>Created</dt>
        <dd>{formatDate(artwork.created_at)}</dd>
      {/if}

      {#if artwork.file_size}
        <dt>File size</dt>
        <dd>{formatFileSize(artwork.file_size)}</dd>
      {/if}

      <dt>Dimensions</dt>
      <dd>{artwork.dimensions}</dd>

      {#if artwork.folder}
        <dt>Folder</dt>
        <dd class="break-all">{artwork.folder}</dd>
      {/if}

      {#if artwork.ocr_word_count}
        <dt>OCR words</dt>
        <dd>{artwork.ocr_word_count}</dd>
      {/if}

      {#if artwork.description}
        <dt class="mt-6">Matched text</dt>
        <dd class="whitespace-pre-wrap ocr-preview">{@html highlightOcr(artwork.description, queryTokens)}</dd>
      {/if}

      <dt class="mt-6">File path</dt>
      <dd class="break-all">{artwork.url}</dd>
    {:else}
      <!-- Demo mode: original Dispict-style metadata -->
      <dt>
        Creator{#if artwork.people.length > 1}s{/if}
      </dt>
      <dd>
        {#each artwork.people as name}<p>{name}</p>{:else}Unknown{/each}
      </dd>

      {#if artwork.dated}
        <dt>Date</dt>
        <dd>{artwork.dated}</dd>
      {/if}

      <dt>Medium</dt>
      <dd>
        {#if artwork.technique && artwork.medium}
          {artwork.technique} / {artwork.medium}
        {:else if artwork.technique}
          {artwork.technique}
        {:else if artwork.medium}
          {artwork.medium}
        {:else}
          N/A
        {/if}
      </dd>

      {#if artwork.dimensions}
        <dt>Dimensions</dt>
        <dd class="whitespace-pre-wrap">{artwork.dimensions}</dd>
      {/if}

      <dt class="mt-8">Demo dataset</dt>
      <dd>Curated screenshot demo gallery.</dd>
    {/if}
  </dl>
</div>

<style lang="postcss">
  dt {
    @apply text-xs font-semibold uppercase;
  }

  :global(.bg-stone-900) dt {
    color: theme(colors.stone.400);
  }

  :global(:not(.bg-stone-900)) dt {
    @apply text-neutral-500;
  }

  dd {
    @apply text-sm;
  }

  :global(.bg-stone-900) dd {
    color: theme(colors.stone.200);
  }

  :global(:not(.bg-stone-900)) dd {
    @apply text-neutral-800;
  }

  dd:not(:last-of-type) {
    @apply mb-5;
  }

  .ocr-preview :global(mark) {
    background-color: theme(colors.amber.400 / 40%);
    color: inherit;
    padding: 0 2px;
    border-radius: 2px;
  }
</style>
