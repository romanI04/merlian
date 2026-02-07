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
      class="radial-gradient relative z-30 w-[360px] h-[360px] rounded-full"
      style:left="{$mouseX}px"
      style:top="{$mouseY}px"
      style:transform="translate(-50%, -50%)"
    />
  </div>
{/if}

{#if open}
  <div
    class="fixed z-40 inset-3 sm:inset-6 md:inset-8 rounded-2xl
    backdrop-blur-lg border border-gray-300 bg-gray-50/75
    flex flex-col justify-between items-center px-4 sm:px-6 overflow-y-auto"
    on:mousemove={handleMouse}
    on:wheel={handleWheel}
    in:fade={{ duration: 200 }}
    out:fly={{ y: -height, duration: 1000, easing: sineInOut }}
    bind:clientHeight={height}
    bind:this={welcomeEl}
  >
    {#if init}
      <div class="py-8">
        <h2
          class="text-center text-4xl sm:text-5xl fontvar-heading mb-2 sm:mb-4"
          in:fade={{ delay: 300 }}
        >
          merlian
        </h2>
      </div>

      <div class="max-w-2xl text-center">
        <p
          class="tagline text-4xl md:text-5xl lg:text-6xl xl:text-7xl"
          in:fade={{ delay: 800 }}
        >
          Every screenshot you've ever taken.
          <span class="text-[105%] font-serif italic">Findable in seconds.</span>
        </p>

        <p class="mt-6 text-lg text-gray-600 max-w-lg mx-auto" in:fade={{ delay: 1200 }}>
          Error messages, receipts, confirmation codes, meeting notes —
          type what you remember. Nothing leaves your machine.
        </p>
      </div>

      <div class="py-10 flex flex-col items-center gap-3" in:fade={{ delay: 1800 }}>
        <button
          class="rounded-full px-6 py-2.5 bg-black text-white text-lg
          hover:bg-white hover:text-black hover:ring-1 hover:ring-black
          active:bg-rose-100 active:text-black active:ring-1 active:ring-black transition-colors"
          on:click={() => {
            window.location.hash = "#/demo";
            dispatch("close");
          }}
        >
          Try the demo
        </button>
        <button
          class="rounded-full px-6 py-2.5 bg-white text-black text-lg ring-1 ring-black/20
          hover:ring-black hover:bg-neutral-50 transition-colors"
          on:click={() => {
            window.location.hash = "#/local";
            dispatch("close");
          }}
        >
          Search my own library
        </button>
        <p class="mt-2 text-xs text-gray-500 max-w-md text-center">
          100% local. No cloud. No account. Your files never leave your machine.
        </p>
      </div>
    {/if}
  </div>
{/if}

<style lang="postcss">
  .radial-gradient {
    background: radial-gradient(
      circle at center,
      theme(colors.indigo.600) 0,
      theme(colors.blue.700) 20%,
      theme(colors.green.600) 40%,
      theme(colors.orange.500) 50%,
      theme(colors.pink.500) 60%,
      #ffffff00 100%
    );
    opacity: 60%;
  }

  p.tagline {
    font-variation-settings: "GRAD" 150, "YOPQ" 50, "XTRA" 500, "YTLC" 570;
    @apply tracking-tight;
  }
</style>
