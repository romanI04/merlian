<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import { fade, fly } from "svelte/transition";
  import { sineInOut } from "svelte/easing";
  import { spring } from "svelte/motion";

  const dispatch = createEventDispatcher<{ close: void }>();

  export let open: boolean;
  export let mode: "demo" | "local" = "demo";

  let mouseX = spring<number>(-142);
  let mouseY = spring<number>(-142);
  let height: number;
  let welcomeEl: HTMLDivElement;

  function handleMouse(event: MouseEvent) {
    if ($mouseX == -142) {
      mouseX.set(event.clientX, { hard: true });
      mouseY.set(event.clientY, { hard: true });
    }
    mouseX.set(event.clientX - welcomeEl.offsetLeft);
    mouseY.set(event.clientY - welcomeEl.offsetTop);
  }

  function handleWheel(event: WheelEvent) {
    if (open) {
      event.preventDefault();
      if (event.deltaY > 0) {
        dispatch("close");
      }
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (open) {
      if (["Enter", " ", "Tab", "Escape"].includes(event.key)) {
        event.preventDefault();
        dispatch("close");
      }
    }
  }

  let init = false;
  onMount(() => {
    init = true;
    document.body.addEventListener("keydown", handleKeydown);
    return () => {
      document.body.removeEventListener("keydown", handleKeydown);
    };
  });
</script>

{#if open && $mouseX !== -142}
  <div
    class="fixed z-40 inset-3 sm:inset-6 md:inset-8 rounded-2xl overflow-hidden"
    in:fade={{ duration: 200, delay: 200 }}
    out:fade={{ duration: 150 }}
  >
    <div
      class="radial-gradient relative z-30 w-[420px] h-[420px] rounded-full"
      style:left="{$mouseX}px"
      style:top="{$mouseY}px"
      style:transform="translate(-50%, -50%)"
    />
  </div>
{/if}

{#if open}
  <div
    class="fixed z-40 inset-3 sm:inset-6 md:inset-8 rounded-2xl
    backdrop-blur-xl border border-white/40 bg-white/60
    flex flex-col justify-center items-center px-4 sm:px-6 overflow-y-auto"
    on:mousemove={handleMouse}
    on:wheel={handleWheel}
    in:fade={{ duration: 200 }}
    out:fly={{ y: -height, duration: 1000, easing: sineInOut }}
    bind:clientHeight={height}
    bind:this={welcomeEl}
  >
    {#if init}
      <!-- Wordmark -->
      <div class="mb-2" in:fade={{ delay: 200 }}>
        <span class="text-sm font-medium tracking-[0.2em] uppercase text-neutral-400">merlian</span>
      </div>

      <!-- Hero headline -->
      <div class="max-w-3xl text-center mb-8">
        <h1
          class="hero-headline text-[clamp(2rem,6vw,4.5rem)] leading-[1.05] tracking-tight"
          in:fade={{ delay: 500 }}
        >
          Every screenshot you've ever taken.
          <span class="hero-italic">Findable in seconds.</span>
        </h1>

        <p class="mt-5 text-base sm:text-lg text-neutral-500 max-w-xl mx-auto leading-relaxed" in:fade={{ delay: 900 }}>
          Error messages, receipts, confirmation codes, meeting notes — type what you remember. AI finds the exact image.
        </p>
      </div>

      <!-- Search preview mockup -->
      <div class="w-full max-w-md mb-8" in:fade={{ delay: 1200 }}>
        <div class="search-mockup rounded-xl bg-white/80 border border-neutral-200/60 shadow-lg px-4 py-3">
          <div class="flex items-center gap-3">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-neutral-400 flex-shrink-0"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <span class="text-neutral-400 text-base">error 403 forbidden...</span>
          </div>
          <div class="flex gap-2 mt-2.5">
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-500">receipt total</span>
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-500">confirmation code</span>
            <span class="text-[11px] px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-500">deploy failed</span>
          </div>
        </div>
      </div>

      <!-- CTAs -->
      <div class="flex flex-col sm:flex-row items-center gap-3 mb-6" in:fade={{ delay: 1500 }}>
        <button
          class="group rounded-full px-8 py-3 bg-black text-white text-base font-medium
          hover:bg-neutral-800 active:scale-[0.98] transition-all shadow-lg shadow-black/10"
          on:click={() => {
            window.location.hash = "#/demo";
            dispatch("close");
          }}
        >
          Try the demo
          <span class="inline-block ml-1 group-hover:translate-x-0.5 transition-transform">&rarr;</span>
        </button>
        <button
          class="rounded-full px-8 py-3 text-neutral-700 text-base font-medium
          bg-white/80 ring-1 ring-neutral-200
          hover:ring-neutral-400 hover:bg-white active:scale-[0.98] transition-all"
          on:click={() => {
            window.location.hash = "#/local";
            dispatch("close");
          }}
        >
          Search my library
        </button>
      </div>

      <!-- Trust line -->
      <div class="flex items-center gap-4 text-xs text-neutral-400" in:fade={{ delay: 1800 }}>
        <span class="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          100% local
        </span>
        <span class="w-px h-3 bg-neutral-300"></span>
        <span>No cloud</span>
        <span class="w-px h-3 bg-neutral-300"></span>
        <span>No account</span>
        <span class="w-px h-3 bg-neutral-300"></span>
        <span>Files never leave your machine</span>
      </div>
    {/if}
  </div>
{/if}

<style lang="postcss">
  .radial-gradient {
    background: radial-gradient(
      circle at center,
      theme(colors.violet.500) 0,
      theme(colors.blue.500) 25%,
      theme(colors.cyan.400) 45%,
      theme(colors.emerald.400) 60%,
      #ffffff00 100%
    );
    opacity: 35%;
    filter: blur(40px);
  }

  .hero-headline {
    font-variation-settings: "GRAD" 150, "YOPQ" 50, "XTRA" 500, "YTLC" 570;
    color: theme(colors.neutral.900);
  }

  .hero-italic {
    font-family: "Source Serif 4", Georgia, serif;
    font-style: italic;
    font-size: 105%;
    background: linear-gradient(135deg, theme(colors.violet.600), theme(colors.blue.600));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .search-mockup {
    backdrop-filter: blur(12px);
  }
</style>
