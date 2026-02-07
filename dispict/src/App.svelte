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

  let indexing = false;
  let statusLine = "Checking status…";
  let lastIndexedLabel = "";
  let currentJobId: string | null = null;

  // Multi-folder state
  type DetectedFolder = { path: string; count: number; accessible: boolean; selected: boolean };
  let detectedFolders: DetectedFolder[] = [];
  let customFolder = "";
  let showCustomFolder = false;
  let permissionWarning = "";
  let modelStatus = "";

  // Post-index suggestions
  let suggestedQueries: { query: string; confidence: number }[] = [];
  let showSuggestions = false;
  let artSearchRef: ArtSearch | null = null;

  // Feedback toast — show after 5 searches
  let searchCount = 0;
  let showFeedbackToast = false;
  let feedbackDismissed = false;

  function onSearchPerformed() {
    searchCount++;
    if (searchCount >= 5 && !feedbackDismissed && !showFeedbackToast) {
      showFeedbackToast = true;
    }
  }

  function dismissFeedback() {
    showFeedbackToast = false;
    feedbackDismissed = true;
  }

  // Listen for search events from ArtSearch
  if (typeof window !== "undefined") {
    window.addEventListener("merlian-search-performed", () => onSearchPerformed());
  }

  // Commercial UX principle:
  // - The app surface is for search/browse.
  // - Library/indexing controls live behind an explicit "Library" modal.
  let showLibrary = false;

  function apiBase(): string {
    return LOCAL_API_URL.endsWith("/") ? LOCAL_API_URL.slice(0, -1) : LOCAL_API_URL;
  }

  async function refreshStatus() {
    try {
      const resp = await fetch(apiBase() + "/status");
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
    } catch {
      statusLine = "Local engine not running (start API server on :8008)";
    }
  }

  async function detectFolders() {
    try {
      const resp = await fetch(apiBase() + "/detect-folders");
      const data = await resp.json();
      detectedFolders = (data?.folders ?? []).map((f: any) => ({
        ...f,
        selected: f.accessible && f.count > 0,
      }));
      const denied = detectedFolders.filter(f => !f.accessible);
      if (denied.length > 0) {
        permissionWarning = "Some folders need Full Disk Access permission in System Preferences.";
      }
    } catch {
      detectedFolders = [];
    }
  }

  async function warmModel() {
    try {
      const ws = await fetch(apiBase() + "/warm-status");
      const data = await ws.json();
      if (data.status === "ready") {
        modelStatus = "";
        return;
      }
      modelStatus = data.status === "downloading" ? "Downloading AI model (577 MB)..." : "Loading AI model...";
      // Fire warm in background
      fetch(apiBase() + "/warm", { method: "POST" }).then(() => {
        modelStatus = "";
      }).catch(() => {
        modelStatus = "";
      });
    } catch {
      modelStatus = "";
    }
  }

  async function pickFolder() {
    try {
      const resp = await fetch(apiBase() + "/pick-folder", { method: "POST" });
      const data = await resp.json();
      if (data?.ok && data?.path) {
        customFolder = data.path;
        showCustomFolder = true;
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function cancelIndex() {
    if (!currentJobId) return;
    try {
      await fetch(apiBase() + `/jobs/${currentJobId}/cancel`, { method: "POST" });
      statusLine = "Cancelling…";
    } catch (e) {
      console.error(e);
    }
  }

  async function runIndex(payload: any) {
    indexing = true;
    showSuggestions = false;
    statusLine = payload?.recent_only ? "Building your personal demo…" : "Starting index…";

    try {
      const resp = await fetch(apiBase() + "/index", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();
      const jobId = data?.job_id as string;
      if (!jobId) throw new Error("No job_id returned");
      currentJobId = jobId;

      while (true) {
        const j = await (await fetch(apiBase() + `/jobs/${jobId}`)).json();
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
            statusLine = payload?.recent_only ? "Personal demo ready!" : "Index updated";
          }
          break;
        }
        if (j.status === "error") throw new Error(j.error ?? "Index failed");
        if (j.status === "cancelled") throw new Error("Index cancelled");

        await new Promise((r) => setTimeout(r, 600));
      }

      // Post-index: fetch suggested queries
      await fetchSuggestions();

    } catch (e) {
      statusLine = payload?.recent_only ? "Personal demo failed" : "Index failed";
      console.error(e);
    } finally {
      indexing = false;
      currentJobId = null;
      await refreshStatus();
    }
  }

  async function fetchSuggestions() {
    try {
      const resp = await fetch(apiBase() + "/suggest-queries", { method: "POST" });
      const data = await resp.json();
      suggestedQueries = data?.suggestions ?? [];
      if (suggestedQueries.length > 0) {
        showSuggestions = true;
      }
    } catch {
      suggestedQueries = [];
    }
  }

  function trySuggestion(query: string) {
    showLibrary = false;
    showSuggestions = false;
    // Dispatch query to ArtSearch via hash trick
    window.dispatchEvent(new CustomEvent("merlian-search", { detail: query }));
  }

  function startPersonalDemo() {
    const selectedPaths = detectedFolders.filter(f => f.selected).map(f => f.path);
    if (showCustomFolder && customFolder) {
      selectedPaths.push(customFolder);
    }
    if (selectedPaths.length === 0) return;
    runIndex({
      folders: selectedPaths,
      ocr: true,
      device: "auto",
      recent_only: true,
      max_items: 200,
    });
  }

  function startFullIndex() {
    const selectedPaths = detectedFolders.filter(f => f.selected).map(f => f.path);
    if (showCustomFolder && customFolder) {
      selectedPaths.push(customFolder);
    }
    if (selectedPaths.length === 0) return;
    runIndex({
      folders: selectedPaths,
      ocr: true,
      device: "auto",
      recent_only: false,
    });
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

  // On Library open: detect folders + warm model
  $: if (showLibrary) {
    detectFolders();
    warmModel();
  }

  refreshStatus();
</script>

<Welcome open={welcome} {mode} on:close={() => (welcome = false)} />

{#if mode === "demo"}
  <nav class="fixed z-50 top-0 left-0 right-0 h-11 px-4 bg-white/70 backdrop-blur-lg border-b border-neutral-100">
    <div class="h-full max-w-5xl mx-auto flex items-center justify-between">
      <button class="flex items-center gap-2 hover:opacity-70 transition-opacity" on:click={() => (welcome = true)}>
        <span class="text-sm font-semibold tracking-tight text-neutral-900">merlian</span>
        <span class="text-[11px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-500 font-medium">demo</span>
      </button>
      <div class="flex items-center gap-1">
        <a
          href="#/local"
          class="text-xs px-3 py-1.5 rounded-lg text-neutral-600 hover:bg-neutral-100 transition-colors font-medium"
        >
          Search my library
        </a>
      </div>
    </div>
  </nav>
{:else}
  <nav class="fixed z-50 top-0 left-0 right-0 h-11 px-4 bg-white/70 backdrop-blur-lg border-b border-neutral-100">
    <div class="h-full max-w-5xl mx-auto flex items-center justify-between">
      <button class="flex items-center gap-2 hover:opacity-70 transition-opacity" on:click={() => (welcome = true)}>
        <span class="text-sm font-semibold tracking-tight text-neutral-900">merlian</span>
      </button>
      <div class="flex items-center gap-1">
        <button
          class="text-xs px-3 py-1.5 rounded-lg text-neutral-600 hover:bg-neutral-100 transition-colors font-medium"
          on:click={() => (showLibrary = true)}
        >
          Library
        </button>
        <a
          href="#/demo"
          class="text-xs px-3 py-1.5 rounded-lg text-neutral-600 hover:bg-neutral-100 transition-colors font-medium"
        >
          Demo
        </a>
      </div>
    </div>
  </nav>
{/if}

<!-- Main app surface: search/browse only -->
<ArtSearch {mode} bind:this={artSearchRef} />

<!-- Library modal: indexing / personal demo setup -->
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
          {#if modelStatus}
            <div class="text-[11px] text-blue-600 mt-1">{modelStatus}</div>
          {/if}
        </div>
        <button class="px-3 py-1.5 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-50" on:click={() => (showLibrary = false)}>
          Close
        </button>
      </div>

      <div class="mt-4 grid gap-3">
        <!-- Multi-folder checkboxes -->
        {#if detectedFolders.length > 0}
          <div>
            <div class="text-[11px] text-neutral-500 mb-2">Select folders to index</div>
            {#each detectedFolders as folder}
              <label class="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-neutral-50 cursor-pointer {!folder.accessible ? 'opacity-50' : ''}">
                <input
                  type="checkbox"
                  bind:checked={folder.selected}
                  disabled={!folder.accessible || indexing}
                  class="rounded border-neutral-300"
                />
                <span class="font-mono text-xs flex-1 break-all">{folder.path}</span>
                <span class="text-[11px] text-neutral-400">
                  {#if !folder.accessible}
                    <span class="text-red-500">no access</span>
                  {:else}
                    {folder.count} images
                  {/if}
                </span>
              </label>
            {/each}
          </div>
        {/if}

        {#if permissionWarning}
          <div class="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 border border-amber-200">
            {permissionWarning}
          </div>
        {/if}

        {#if showCustomFolder}
          <div>
            <div class="text-[11px] text-neutral-500 mb-1">Custom folder</div>
            <input
              class="w-full px-3 py-2 rounded-lg border border-neutral-200 bg-white focus:outline-none focus:ring-2 focus:ring-black/10 font-mono text-xs"
              bind:value={customFolder}
              placeholder="/path/to/folder"
            />
          </div>
        {/if}

        <div class="flex flex-wrap gap-2">
          <button class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={pickFolder} disabled={indexing}>
            Add folder…
          </button>
          {#if !showCustomFolder}
            <button class="px-3 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={() => (showCustomFolder = true)}>
              Custom path
            </button>
          {/if}
          <button
            class="px-4 py-2 rounded-lg bg-neutral-900 text-white hover:bg-neutral-700 disabled:opacity-50"
            on:click={startPersonalDemo}
            disabled={indexing || detectedFolders.filter(f => f.selected).length === 0}
            title="Index last 200 screenshots (fast) so you can try search immediately">
            {indexing ? "Building…" : "Build personal demo"}
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100 disabled:opacity-50"
            on:click={startFullIndex}
            disabled={indexing || detectedFolders.filter(f => f.selected).length === 0}>
            Full index
          </button>
          {#if indexing}
            <button class="px-4 py-2 rounded-lg bg-white border border-neutral-200 hover:bg-neutral-100" on:click={cancelIndex}>
              Cancel
            </button>
          {/if}
        </div>

        <!-- Post-index suggested queries -->
        {#if showSuggestions && suggestedQueries.length > 0}
          <div class="mt-2 p-3 bg-green-50 rounded-lg border border-green-200">
            <div class="text-xs font-medium text-green-800 mb-2">Your library looks great! Try searching:</div>
            <div class="flex flex-wrap gap-2">
              {#each suggestedQueries as sq}
                <button
                  class="px-3 py-1.5 rounded-full bg-white border border-green-300 hover:bg-green-100 text-sm text-green-800"
                  on:click={() => trySuggestion(sq.query)}
                >
                  {sq.query}
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <p class="text-[11px] text-neutral-500">
          100% local. Nothing leaves your machine. Your files are never uploaded.
        </p>
      </div>
    </div>
  </div>
{/if}


<!-- Feedback toast -->
{#if showFeedbackToast}
  <div class="fixed z-[80] bottom-6 right-6 max-w-sm bg-white border border-neutral-200 shadow-lg rounded-xl p-4 animate-slide-up">
    <div class="flex items-start gap-3">
      <div class="flex-1">
        <div class="text-sm font-medium text-neutral-900">Finding useful things?</div>
        <div class="text-xs text-neutral-500 mt-1">We'd love 2 minutes of your feedback to make Merlian better.</div>
        <div class="flex gap-2 mt-3">
          <a
            href="https://tally.so/r/merlian-feedback"
            target="_blank"
            rel="noopener noreferrer"
            class="px-3 py-1.5 text-xs font-medium bg-black text-white rounded-lg hover:bg-neutral-800"
          >
            Share feedback
          </a>
          <button
            class="px-3 py-1.5 text-xs text-neutral-500 hover:text-neutral-700"
            on:click={dismissFeedback}
          >
            Maybe later
          </button>
        </div>
      </div>
      <button class="text-neutral-400 hover:text-neutral-600 text-lg leading-none" on:click={dismissFeedback}>&times;</button>
    </div>
  </div>
{/if}

<style lang="postcss">
  :global(.animate-slide-up) {
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(16px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
