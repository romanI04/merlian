<script lang="ts">
  import { onMount } from "svelte";
  import { cubicOut } from "svelte/easing";
  import { fade, fly } from "svelte/transition";
  import debounce from "lodash.debounce";

  import ArtImage from "./ArtImage.svelte";
  import SearchInput from "./SearchInput.svelte";
  import Sidebar from "./Sidebar.svelte";
  import { loadSuggestions, setSearchMode, type Artwork, type SearchResult, type SearchMode } from "./api";

  export let mode: SearchMode = "demo";
  $: setSearchMode(mode);

  import { layoutArtwork, PIXELS_PER_CM } from "./geometry";
  import { TouchZoom } from "./touchZoom";

  const SIDEBAR_WIDTH = 420;

  const LOCAL_STARTER_INPUTS = [
    "error 403",
    "invoice total",
    "meeting notes",
    "dark mode dashboard",
    "code editor",
    "google docs",
    "calendar screenshot",
    "map route",
  ];

  const DEMO_STARTER_INPUTS = [
    "bauhaus letterhead",
    "minimalist black logo",
    "abstract painting",
    "portrait with red",
    "architectural blueprint",
    "typography poster",
    "still life with fruit",
    "ink drawing",
  ];

  function starterInputs(): string[] {
    return mode === "local" ? LOCAL_STARTER_INPUTS : DEMO_STARTER_INPUTS;
  }

  function randomInput(exclude?: string) {
    const arr = starterInputs();
    while (true) {
      const value = arr[Math.floor(Math.random() * arr.length)];
      if (value !== exclude) return value;
    }
  }

  let query = randomInput(); // @hmr:keep

  // Force an instant "wow" query on load for demo gallery.
  onMount(() => {
    if (mode === "demo") query = "bauhaus letterhead";
  });

  let frame: HTMLDivElement;
  let touchZoom: TouchZoom;
  let center = [0, 0];
  let zoom = 1;
  let lastMove = 0;

  let selected: Artwork | null = null;

  onMount(() => {
    touchZoom = new TouchZoom(frame);
    touchZoom.onMove((manual) => {
      center = touchZoom.center;
      zoom = touchZoom.zoom;
      if (manual) {
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
        lastMove = Date.now();
        selected = null;
      }
    });
  });

  function getTransform(pos: number[], center: number[], zoom: number): string {
    return `scale(${(zoom * 100).toFixed(3)}%) translate(
      ${pos[0] * PIXELS_PER_CM - center[0]}px,
      ${pos[1] * PIXELS_PER_CM - center[1]}px
    )`;
  }

  /** Adaptively adjust image size based on visibility and screen size. */
  function getDetail(
    artwork: Artwork,
    pos: number[],
    center: number[],
    zoom: number
  ): number {
    const pxBounding = [
      zoom * ((pos[0] - artwork.dimwidth / 2) * PIXELS_PER_CM - center[0]),
      zoom * ((pos[0] + artwork.dimwidth / 2) * PIXELS_PER_CM - center[0]),
      zoom * ((pos[1] - artwork.dimheight / 2) * PIXELS_PER_CM - center[1]),
      zoom * ((pos[1] + artwork.dimheight / 2) * PIXELS_PER_CM - center[1]),
    ];
    const windowSize = [
      -frame.clientWidth / 2,
      frame.clientWidth / 2,
      -frame.clientHeight / 2,
      frame.clientHeight / 2,
    ];
    const physicalWidth =
      window.devicePixelRatio * zoom * artwork.dimwidth * PIXELS_PER_CM;
    // Not visible, outside the window.
    if (
      pxBounding[0] > 1.15 * windowSize[1] ||
      pxBounding[1] < 1.15 * windowSize[0] ||
      pxBounding[2] > 1.15 * windowSize[3] ||
      pxBounding[3] < 1.15 * windowSize[2]
    ) {
      return 400;
    } else if (physicalWidth < 400) {
      return 400;
    } else if (physicalWidth < 800) {
      return 800;
    } else {
      return 4000; // full size
    }
  }

  /** Handle when an artwork is selected for more details. */
  function handleSelect(artwork: Artwork, pos: [number, number]) {
    if (lastMove < Date.now() - 50 && !touchZoom.isPinching) {
      const sidebarOffset =
        frame.clientWidth > SIDEBAR_WIDTH ? SIDEBAR_WIDTH : 0;
      const desiredZoom =
        0.8 *
        Math.min(
          frame.clientHeight / (artwork.dimheight * PIXELS_PER_CM),
          (frame.clientWidth - sidebarOffset) /
            (artwork.dimwidth * PIXELS_PER_CM)
        );

      touchZoom.moveTo(
        [
          pos[0] * PIXELS_PER_CM + (0.5 * sidebarOffset) / desiredZoom,
          pos[1] * PIXELS_PER_CM,
        ],
        desiredZoom
      );
      selected = artwork;
    }
  }

  let results: SearchResult[] = [];
  let apiError: string | null = null;
  let searching = 0;
  let abortController = new AbortController();

  async function retry() {
    apiError = null;
    await updateResults(query);
  }

  async function updateResults(query: string) {
    selected = null;
    searching++;
    abortController.abort();
    const ctrl = new AbortController();
    abortController = ctrl;
    // Keep previous results while loading new ones.
    try {
      if (!query?.trim()) return;
      results = await loadSuggestions(query, 64, ctrl.signal);
      apiError = null;
    } catch (error: any) {
      if (!ctrl.signal.aborted) {
        apiError =
          "Search is temporarily unavailable (demo backend). Please try again.";
      }
    } finally {
      searching--;
    }
  }

  const updateResultsDebounced = debounce(updateResults, 150);
  $: updateResultsDebounced(query);

  $: positions = layoutArtwork(results.map((r) => r.artwork));
</script>

<main class="absolute inset-0 overflow-hidden bg-neutral-50">
  <div
    class="w-full h-full flex justify-center items-center touch-none"
    bind:this={frame}
  >
    <div style:transform={getTransform([0, 0], center, zoom)}>
      <SearchInput
        bind:value={query}
        {mode}
        searching={searching > 0}
        on:refresh={() => (query = randomInput(query))}
      />
      {#if apiError}
        <div
          class="absolute text-center w-[420px] max-w-[90vw] mt-3 p-2 rounded-xl bg-red-500/10 text-red-900 border border-red-500/20"
        >
          <p class="text-sm">{apiError}</p>
          <button
            class="mt-2 text-xs px-2 py-1 rounded-md bg-white/80 hover:bg-white border border-red-500/20"
            on:click={retry}
          >
            Try again
          </button>
        </div>
      {/if}
    </div>

    {#each results as result, i (result)}
      {@const detail = getDetail(result.artwork, positions[i], center, zoom)}
      <div
        class="absolute"
        style:transform={getTransform(positions[i], center, zoom)}
        transition:fade
      >
        <button
          class="cursor-default"
          on:click={() => handleSelect(result.artwork, positions[i])}
          on:touchend={() => handleSelect(result.artwork, positions[i])}
        >
          <ArtImage
            artwork={result.artwork}
            {detail}
            grayed={Boolean(selected) && selected !== result.artwork}
          />
        </button>
      </div>
    {/each}
  </div>
</main>

{#if selected}
  <aside
    class="absolute z-20 inset-y-0 right-0 bg-white/90 backdrop-blur border-l border-neutral-200 shadow-xl overflow-y-auto"
    style:width="calc(min(100vw, {SIDEBAR_WIDTH}px))"
    transition:fly={{ x: SIDEBAR_WIDTH, y: 0, duration: 300, easing: cubicOut }}
  >
    <Sidebar artwork={selected} on:close={() => (selected = null)} />
  </aside>
{/if}
