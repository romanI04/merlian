<script lang="ts">
  import ArtSearch from "./lib/ArtSearch.svelte";
  import Welcome from "./lib/Welcome.svelte";
  import type { SearchMode } from "./lib/api";

  const navigationType = (
    window.performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming
  )?.type;

  // Only show the welcome overlay on a fresh navigation (marketing), not as part of the app UI.
  let welcome = !navigationType || navigationType === "navigate"; // @hmr:keep

  const LOCAL_API_URL =
    // @ts-ignore
    (import.meta as any).env?.VITE_LOCAL_API_URL ?? "http://127.0.0.1:8008";

  let folderInput: string = "~/Desktop";
  let indexing = false;
  let statusLine = "Checking status…";
  let lastIndexedLabel = "";
  let currentJobId: string | null = null;
  let showAdvancedPath = false;

  // Commercial UX principle:
  // - The app surface is for search/browse.
  // - Library/indexing controls live behind an explicit "Library" modal.
  let showLibrary = false;

  async function refreshStatus() {
    try {
      const base = LOCAL_API_URL.endsWith("/") ? LOCAL_API_URL.slice(0, -1) : LOCAL_API_URL;
      const resp = await fetch(base + "/status");
      const data = await resp.json();
      if (!data?.indexed) {
        statusLine = "Not indexed yet";
        return;
      }
      statusLine = `Indexed ${data.assets} items • OCR ${data.with_ocr}/${data.assets}`;
      if (data.last_indexed_at) {
        try {
          const dt = new Date(data.last_indexed_at);
          lastIndexedLabel = `Last indexed: ${dt.toLocaleString()}`;
        } catch {
          lastIndexedLabel = "";
        }
      } else {
        lastIndexedLabel = "";
      }
      if (data.root) folderInput = data.root;
    } catch {
      statusLine = "Local engine not running (start API server on :8008)";
    }
  }

  async function pickFolder() {
    const base = LOCAL_API_URL.endsWith("/") ? LOCAL_API_URL.slice(0, -1) : LOCAL_API_URL;
    try {
      const resp = await fetch(base + "/pick-folder", { method: "POST" });
      const data = await resp.json();
      if (data?.ok && data?.path) folderInput = data.path;
    } catch (e) {
      console.error(e);
    }
  }

  async function cancelIndex() {
    if (!currentJobId) return;
    const base = LOCAL_API_URL.endsWith("/") ? LOCAL_API_URL.slice(0, -1) : LOCAL_API_URL;
    try {
      await fetch(base + `/jobs/${currentJobId}/cancel`, { method: "POST" });
      statusLine = "Cancelling…";
    } catch (e) {
      console.error(e);
    }
  }

  async function runIndex(payload: any) {
    indexing = true;
    statusLine = payload?.recent_only ? "Building your personal demo…" : "Starting index…";

    const base = LOCAL_API_URL.endsWith("/") ? LOCAL_API_URL.slice(0, -1) : LOCAL_API_URL;

    try {
      const resp = await fetch(base + "/index", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();
      const jobId = data?.job_id as string;
      if (!jobId) throw new Error("No job_id returned");
      currentJobId = jobId;

      while (true) {
        const j = await (await fetch(base + `/jobs/${jobId}`)).json();
        if (j.total) {
          statusLine = `${payload?.recent_only ? "Building personal demo" : "Indexing"}… ${j.processed}/${j.total}`;
        } else {
          statusLine = j.message ?? (payload?.recent_only ? "Building personal demo…" : "Indexing…");
        }

        if (j.status === "done") {
          const msg = (j.message as string) || "";
          if (!payload?.recent_only && msg.includes("+0 new") && msg.includes("~0 updated") && msg.includes("-0 removed")) {
            statusLine = "Index up to date";
          } else {
            statusLine = payload?.recent_only ? "Personal demo ready" : "Index updated";
          }
          break;
        }
        if (j.status === "error") throw new Error(j.error ?? "Index failed");
        if (j.status === "cancelled") throw new Error("Index cancelled");

        await new Promise((r) => setTimeout(r, 600));
      }
    } catch (e) {
      statusLine = payload?.recent_only ? "Personal demo failed" : "Index failed";
      console.error(e);
    } finally {
      indexing = false;
      currentJobId = null;
      await refreshStatus();
    }
  }

  function parseMode(): SearchMode {
    const h = window.location.hash || "";
    if (h.includes("local")) return "local";
    return "demo";
  }

  let mode: SearchMode = parseMode();
  window.addEventListener("hashchange", () => {
    mode = parseMode();
  });

  refreshStatus();
</script>

<Welcome open={welcome} {mode} on:close={() => (welcome = false)} />

{#if mode === "demo"}
  <div class="fixed z-50 top-0 left-0 right-0 px-4 py-2 text-xs sm:text-sm bg-white/80 backdrop-blur border-b border-neutral-200">
    <div class="max-w-3xl mx-auto text-neutral-700 flex items-center justify-between gap-4">
      <div class="truncate">
        <span class="font-medium">Merlian demo gallery</span> — Harvard Art Museums dataset.
      </div>

      <div class="flex items-center gap-4">
        <a class="underline underline-offset-2" href="#/local">Local app</a>
        <a
          class="shrink-0 text-neutral-500 hover:text-neutral-900 underline underline-offset-2"
          target="_blank"
          rel="noopener noreferrer"
          href="https://github.com/romanI04/merlian/blob/main/CREDITS.md">Credits</a>
      </div>
    </div>
  </div>
{:else}
  <div class="fixed z-50 top-0 left-0 right-0 px-4 py-2 text-xs sm:text-sm bg-white/80 backdrop-blur border-b border-neutral-200">
    <div class="max-w-3xl mx-auto text-neutral-700 flex items-center justify-between gap-4">
      <div class="truncate">
        <span class="font-medium">Merlian</span> — local screenshot search.
      </div>

      <div class="flex items-center gap-4">
        <button class="underline underline-offset-2" on:click={() => (showLibrary = true)}>Library</button>
        <a class="underline underline-offset-2" href="#/demo">Demo</a>
      </div>
    </div>
  </div>
{/if}

<!-- Main app surface: search/browse only -->
<ArtSearch {mode} />

<!-- Library modal: indexing / personal demo setup lives here (not on the landing/app surface) -->
{#if mode === "local" && showLibrary}
  <div class="fixed z-[60] inset-0 bg-black/30" on:click={() => (showLibrary = false)} />
  <div class="fixed z-[70] top-16 left-0 right-0 px-4" aria-modal="true" role="dialog">
    <div class="max-w-3xl mx-auto rounded-2xl bg-white border border-neutral-200 shadow-xl p-4 sm:p-5" on:click|stopPropagation>
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="text-base font-medium text-neutral-900">Library</div>
          <div class="text-xs text-neutral-500 mt-0.5">{statusLine}</div>
          {#if lastIndexedLabel}
            <div class="text-[11px] text-neutral-500 mt-1">{lastIndexedLabel}</div>
          {/if}
        </div>
        <button class="px-3 py-1.5 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-50" on:click={() => (showLibrary = false)}>
          Close
        </button>
      </div>

      <div class="mt-4 grid gap-3">
        <div>
          <div class="text-[11px] text-neutral-500 mb-1">Selected folder</div>
          <div class="px-3 py-2 rounded-lg border border-neutral-200 bg-white/80 font-mono text-xs break-all">{folderInput}</div>

          {#if showAdvancedPath}
            <input
              class="mt-2 w-full px-3 py-2 rounded-lg border border-neutral-200 bg-white focus:outline-none focus:ring-2 focus:ring-black/10"
              bind:value={folderInput}
              placeholder="/Users/romanimanov/Desktop" />
          {/if}
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={pickFolder} disabled={indexing}>
            Choose…
          </button>
          <button class="px-3 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={() => (showAdvancedPath = !showAdvancedPath)}>
            {showAdvancedPath ? "Hide" : "Edit"}
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-neutral-900 text-white hover:bg-neutral-700 disabled:opacity-50"
            on:click={() =>
              runIndex({ folder: folderInput, ocr: true, device: "auto", recent_only: false })}
            disabled={indexing}>
            {indexing ? "Indexing…" : "Index"}
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100 disabled:opacity-50"
            on:click={() =>
              runIndex({ folder: folderInput, ocr: true, device: "auto", recent_only: true, max_items: 200 })}
            disabled={indexing}
            title="Indexes a small recent sample (fast) so you can try search immediately">
            Build personal demo
          </button>
          {#if indexing}
            <button class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={cancelIndex}>
              Cancel
            </button>
          {/if}
        </div>

        <div class="flex flex-wrap gap-2 text-xs">
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Desktop")}>Desktop</button>
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Downloads")}>Downloads</button>
          <button class="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200" on:click={() => (folderInput = "~/Pictures")}>Pictures</button>
        </div>

        <p class="text-[11px] text-neutral-500">
          Tip: after indexing, try searches like <span class="font-medium">"error"</span>, <span class="font-medium">"receipt total"</span>, <span class="font-medium">"confirmation code"</span>.
        </p>
      </div>
    </div>
  </div>
{/if}

<div class="absolute top-12 left-4 sm:top-16 sm:left-8">
  <button class="logo-btn text-3xl fontvar-heading" on:click={() => (welcome = true)}>merlian</button>
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
