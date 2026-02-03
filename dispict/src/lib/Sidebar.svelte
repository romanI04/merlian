<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Artwork } from "./api";

  const LOCAL_API_URL =
    // @ts-ignore
    (import.meta as any).env?.VITE_LOCAL_API_URL ?? "http://127.0.0.1:8008";

  const dispatch = createEventDispatcher<{ close: void }>();

  export let artwork: Artwork;

  $: isLocal = Boolean(artwork?.url?.startsWith("/") && !artwork?.url?.startsWith("http"));
</script>

<div class="text-neutral-900 p-6">
  <div class="flex justify-end mb-4">
    <button
      on:click={() => dispatch("close")}
      class="p-1 rounded-md hover:bg-neutral-200"
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
    <p class="text-neutral-500 text-sm">{artwork.objectnumber}</p>

    {#if isLocal}
      <div class="flex gap-2 mt-4">
        <button
          class="inline-block px-3 py-1.5 bg-neutral-900 text-white hover:bg-neutral-700 rounded-md"
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
          class="inline-block px-3 py-1.5 bg-white border border-neutral-200 hover:bg-neutral-100 rounded-md"
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
          Reveal
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

    {#if isLocal && artwork.description}
      <dt>Matched text</dt>
      <dd class="whitespace-pre-wrap text-neutral-700">{artwork.description}</dd>
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

    {#if isLocal}
      <dt class="mt-8">File</dt>
      <dd class="text-neutral-600 break-all">{artwork.url}</dd>
    {:else}
      <dt class="mt-8">Demo dataset</dt>
      <dd class="text-neutral-600">
        Harvard Art Museums demo gallery.
      </dd>
    {/if}
  </dl>
</div>

<style lang="postcss">
  dt {
    @apply text-xs font-semibold uppercase text-neutral-500;
  }

  dd {
    @apply text-neutral-800 text-sm;
  }

  dd:not(:last-of-type) {
    @apply mb-5;
  }
</style>
