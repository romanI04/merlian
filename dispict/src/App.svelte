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

  const LOCAL_API_URL =
    // @ts-ignore
    (import.meta as any).env?.VITE_LOCAL_API_URL ?? "http://127.0.0.1:8008";

  let folderInput: string = "~/Desktop";
  let indexing = false;
  let statusLine = "Checking status…";
  let currentJobId: string | null = null;

  async function refreshStatus() {
    try {
      const base = LOCAL_API_URL.endsWith("/")
        ? LOCAL_API_URL.slice(0, -1)
        : LOCAL_API_URL;
      const resp = await fetch(base + "/status");
      const data = await resp.json();
      if (!data?.indexed) {
        statusLine = "Not indexed yet";
        return;
      }
      statusLine = `Indexed ${data.assets} items • OCR ${data.with_ocr}/${data.assets}`;
      if (data.root) folderInput = data.root;
    } catch {
      statusLine = "Local engine not running (start API server on :8008)";
    }
  }

  async function cancelIndex() {
    if (!currentJobId) return;
    const base = LOCAL_API_URL.endsWith("/")
      ? LOCAL_API_URL.slice(0, -1)
      : LOCAL_API_URL;

    try {
      await fetch(base + `/jobs/${currentJobId}/cancel`, { method: "POST" });
      statusLine = "Cancelling…";
    } catch (e) {
      console.error(e);
    }
  }

  async function runIndex() {
    indexing = true;
    statusLine = "Starting index…";

    const base = LOCAL_API_URL.endsWith("/")
      ? LOCAL_API_URL.slice(0, -1)
      : LOCAL_API_URL;

    try {
      const resp = await fetch(base + "/index", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ folder: folderInput, ocr: true, device: "auto" }),
      });

      const data = await resp.json();
      const jobId = data?.job_id as string;
      if (!jobId) throw new Error("No job_id returned");
      currentJobId = jobId;

      while (true) {
        const j = await (await fetch(base + `/jobs/${jobId}`)).json();
        if (j.total) {
          statusLine = `Indexing… ${j.processed}/${j.total}`;
        } else {
          statusLine = j.message ?? "Indexing…";
        }

        if (j.status === "done") break;
        if (j.status === "error") throw new Error(j.error ?? "Index failed");
        if (j.status === "cancelled") throw new Error("Index cancelled");

        await new Promise((r) => setTimeout(r, 600));
      }

      statusLine = "Index complete";
    } catch (e) {
      statusLine = `Index failed`; // keep it simple in UI
      console.error(e);
    } finally {
      indexing = false;
      currentJobId = null;
      await refreshStatus();
    }
  }

  refreshStatus();

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
        <span class="font-medium">Merlian (local)</span> — search your own library.
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

{#if mode === "local"}
  <div class="fixed z-40 top-10 sm:top-12 left-0 right-0 px-4">
    <div class="max-w-3xl mx-auto">
      <div class="rounded-xl bg-white/90 backdrop-blur border border-neutral-200 shadow-sm p-3 sm:p-4">
        <div class="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
          <div class="text-sm text-neutral-700">
            <span class="font-medium">Index a folder</span>
            <span class="text-neutral-500">(local, stays on your machine)</span>
          </div>
          <div class="text-xs text-neutral-500">
            {statusLine}
          </div>
        </div>

        <div class="mt-3 flex flex-col sm:flex-row gap-2">
          <input
            class="flex-1 px-3 py-2 rounded-lg border border-neutral-200 bg-white focus:outline-none focus:ring-2 focus:ring-black/10"
            bind:value={folderInput}
            placeholder="/Users/romanimanov/Desktop"
          />
          <div class="flex gap-2">
            <button
              class="px-4 py-2 rounded-lg bg-neutral-900 text-white hover:bg-neutral-700 disabled:opacity-50"
              on:click={runIndex}
              disabled={indexing}
            >
              {indexing ? "Indexing…" : "Index"}
            </button>

            {#if indexing}
              <button
                class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100"
                on:click={cancelIndex}
              >
                Cancel
              </button>
            {/if}
          </div>
        </div>

        <div class="mt-2 flex flex-wrap gap-2 text-xs">
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Desktop")}>Desktop</button>
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Downloads")}>Downloads</button>
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Pictures")}>Pictures</button>
        </div>

        <p class="mt-2 text-[11px] text-neutral-500">
          After indexing, try searches like: <span class="font-medium">"error 403"</span>, <span class="font-medium">"invoice total"</span>, <span class="font-medium">"meeting notes"</span>.
        </p>
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
