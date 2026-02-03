<script lang="ts">
  import ArtSearch from "./lib/ArtSearch.svelte";
  import Welcome from "./lib/Welcome.svelte";

  const navigationType = (
    window.performance.getEntriesByType(
      "navigation"
    )[0] as PerformanceNavigationTiming
  )?.type;

  let welcome = !navigationType || navigationType === "navigate"; // @hmr:keep
</script>

<Welcome open={welcome} on:close={() => (welcome = false)} />

<!-- Demo dataset attribution (keep this visible in demo mode) -->
<div
  class="fixed z-50 top-0 left-0 right-0 px-4 py-2 text-xs sm:text-sm bg-white/80 backdrop-blur border-b border-neutral-200"
>
  <div class="max-w-3xl mx-auto text-neutral-700 flex items-center justify-between gap-4">
    <div class="truncate">
      <span class="font-medium">Merlian demo</span> — demo artworks/data from
      <a
        class="underline underline-offset-2"
        target="_blank"
        rel="noopener noreferrer"
        href="https://harvardartmuseums.org"
        >Harvard Art Museums</a
      >.
    </div>

    <a
      class="shrink-0 text-neutral-500 hover:text-neutral-900 underline underline-offset-2"
      target="_blank"
      rel="noopener noreferrer"
      href="https://github.com/romanI04/merlian/blob/main/CREDITS.md"
      >Credits</a
    >
  </div>
</div>

<ArtSearch />

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
