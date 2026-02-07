<script lang="ts">
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher<{ refresh: void }>();

  export let value: string = "";
  export let searching: boolean = false;

  export let mode: "demo" | "local" = "demo";

  const EXAMPLE_SEARCHES_DEMO = [
    "error message",
    "receipt total",
    "confirmation code",
    "dashboard chart",
    "terminal output",
  ];

  const EXAMPLE_SEARCHES_LOCAL = [
    "error 403",
    "receipt total",
    "confirmation code",
    "meeting invite",
    "deploy failed",
  ];

  $: EXAMPLE_SEARCHES = mode === "local" ? EXAMPLE_SEARCHES_LOCAL : EXAMPLE_SEARCHES_DEMO;

  function handleKeydown(event: KeyboardEvent) {
    if (event.ctrlKey || event.metaKey) {
      // Disable formatting shortcuts.
      if (["b", "i", "u"].includes(event.key)) {
        event.preventDefault();
      }
    }
  }

  function handlePaste(event: ClipboardEvent) {
    event.preventDefault();
    var text = event.clipboardData.getData("text/plain");
    const selection = window.getSelection();
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    range.collapse();
    value = (event.target as HTMLTextAreaElement).textContent;
  }
</script>

<div
  class="search-container relative w-[440px] max-w-[90vw] max-h-[200px] rounded-2xl z-10
  bg-white/95 backdrop-blur-lg border border-neutral-200/80
  shadow-lg shadow-black/5 hover:shadow-xl hover:shadow-black/8
  transition-shadow overflow-y-auto"
  on:mousedown={(event) => event.stopPropagation()}
  on:touchstart={(event) => event.stopPropagation()}
  on:dblclick={(event) => event.stopPropagation()}
>
  <div class="flex items-start gap-2 px-4 pt-3.5">
    <!-- Search icon -->
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="text-neutral-300 flex-shrink-0 mt-0.5"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>

    <!-- svelte-ignore a11y-autofocus -->
    <div
      contenteditable
      autofocus
      class="search flex-1"
      bind:textContent={value}
      on:keydown={handleKeydown}
      on:paste={handlePaste}
    />
  </div>

  <div class="px-4 pb-3 pt-2">
    <div class="flex flex-wrap gap-1.5">
      {#each EXAMPLE_SEARCHES as example}
        <button
          class="text-[11px] px-2.5 py-1 rounded-full bg-neutral-50 hover:bg-neutral-100
          text-neutral-500 hover:text-neutral-700 transition-colors border border-transparent hover:border-neutral-200"
          on:click={() => (value = example)}
        >
          {example}
        </button>
      {/each}
    </div>
  </div>

  {#if searching}
    <div
      class="absolute right-3 top-3.5 animate-spin pointer-events-none text-neutral-300"
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
        ><line x1="12" y1="2" x2="12" y2="6" /><line
          x1="12"
          y1="18"
          x2="12"
          y2="22"
        /><line x1="4.93" y1="4.93" x2="7.76" y2="7.76" /><line
          x1="16.24"
          y1="16.24"
          x2="19.07"
          y2="19.07"
        /><line x1="2" y1="12" x2="6" y2="12" /><line
          x1="18"
          y1="12"
          x2="22"
          y2="12"
        /><line x1="4.93" y1="19.07" x2="7.76" y2="16.24" /><line
          x1="16.24"
          y1="7.76"
          x2="19.07"
          y2="4.93"
        /></svg
      >
    </div>
  {:else}
    <button
      class="absolute right-2 top-3 p-1.5 text-neutral-300 hover:text-neutral-500 transition-colors rounded-lg hover:bg-neutral-50"
      on:click={() => dispatch("refresh")}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><polyline points="23 4 23 10 17 10" /><polyline
          points="1 20 1 14 7 14"
        /><path
          d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
        /></svg
      >
    </button>
  {/if}
</div>

<style lang="postcss">
  .search {
    @apply font-sans text-base leading-6 text-left outline-none py-0;
    min-height: 1.5em;
  }

  .search:empty::before {
    content: "Type what you remember...";
    @apply text-neutral-400;
  }

  [contenteditable] :global b {
    font-weight: inherit;
  }

  [contenteditable] :global i {
    font-style: inherit;
  }

  [contenteditable] :global img {
    display: none;
  }
</style>
