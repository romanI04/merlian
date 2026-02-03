<script lang="ts">
  import ArtSearch from "./lib/ArtSearch.svelte";
  import Welcome from "./lib/Welcome.svelte";
  import type { SearchMode } from "./lib/api";

  const navigationType = (
    window.performance.getEntriesByType(
      "navigation"
    )[0] as PerformanceNavigationTiming
  )?.type;

  let welcome = !navigationType || navigationType === "navigate"; // @hmr:keep

  function parseMode(): SearchMode {
    const h = window.location.hash || "";
    if (h.includes("local")) return "local";
    return "demo";
  }

  let mode: SearchMode = parseMode();

  window.addEventListener("hashchange", () => {
    mode = parseMode();
  });
</script>

<Welcome open={welcome} {mode} on:close={() => (welcome = false)} />

{#if mode === "demo"}
  <!-- Harvard demo (marketing) -->
  <div
    class="fixed z-50 top-0 left-0 right-0 px-4 py-2 text-xs sm:text-sm bg-white/80 backdrop-blur border-b border-neutral-200"
  >
    <div class="max-w-3xl mx-auto text-neutral-700 flex items-center justify-between gap-4">
      <div class="truncate">
        <span class="font-medium">Merlian demo gallery</span> — Harvard Art Museums dataset.
      </div>

      <div class="flex items-center gap-4">
        <a class="underline underline-offset-2" href="#/local">Local search</a>
        <a
          class="shrink-0 text-neutral-500 hover:text-neutral-900 underline underline-offset-2"
          target="_blank"
          rel="noopener noreferrer"
          href="https://github.com/romanI04/merlian/blob/main/CREDITS.md"
          >Credits</a
        >
      </div>
    </div>
  </div>
{:else}
  <!-- Local-first product mode -->
  <div
    class="fixed z-50 top-0 left-0 right-0 px-4 py-2 text-xs sm:text-sm bg-white/80 backdrop-blur border-b border-neutral-200"
  >
    <div class="max-w-3xl mx-auto text-neutral-700 flex items-center justify-between gap-4">
      <div class="truncate">
        <span class="font-medium">Merlian (local)</span> — searching your indexed files.
      </div>

      <div class="flex items-center gap-4">
        <a class="underline underline-offset-2" href="#/demo">Demo gallery</a>
        <a
          class="shrink-0 text-neutral-500 hover:text-neutral-900 underline underline-offset-2"
          target="_blank"
          rel="noopener noreferrer"
          href="https://github.com/romanI04/merlian/blob/main/engine/README.md"
          >How to run</a
        >
      </div>
    </div>
  </div>
{/if}

<ArtSearch {mode} />

<div class="absolute top-12 left-4 sm:top-16 sm:left-8">
  <button
    class="logo-btn text-3xl fontvar-heading"
    on:click={() => (welcome = true)}>merlian</button
  >
</div>

<style lang="postcss">
  .logo-btn {
    outline: none;
    transition: text-shadow 200ms;
  }

  .logo-btn:hover {
    text-shadow: 0 0 6px rgba(0, 0, 0, 25%);
  }
</style>
