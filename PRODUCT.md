# Merlian — Product (v1)

## One-liner
**Merlian is a local-first visual memory app for screenshots and images.** Type what you remember → get the exact capture instantly, with evidence (OCR highlight) and one-click actions.

## ICP (v1)
**Screenshot power users on macOS** who routinely capture information to “remember later”:
- Engineers (errors, configs, dashboards, docs)
- PM/ops/analysts (admin panels, metrics, receipts, confirmations)
- Students/researchers (slides, papers, charts)

Common trait: they take screenshots as a memory prosthetic, then can’t reliably retrieve them.

## Job-to-be-done
> “I need to retrieve visual evidence I captured in the past using the way I remember it (meaning / words / fragments), in seconds — without organizing files.”

## Why now / why Merlian
- Existing tools (Finder/Spotlight/Photos) are **path/filename-first**.
- Cloud AI search has a **privacy/trust ceiling** for work screenshots.
- Users won’t organize manually; they will pay for a system that turns screenshot chaos into retrievable evidence.

## Product promise (the contract)
- **Local-only**: user files never leave the machine.
- **Fast**: after warm, top results feel instant (<500ms target).
- **Evidence-first**: results show *why* they matched (OCR snippet/highlight), not “AI guessed.”
- **Actionable**: open/reveal/copy in one click.

## Core loop
1) User grants access to Screenshots (or chooses a folder)
2) Merlian indexes incrementally (OCR + embeddings + thumbnails)
3) User searches in plain language
4) Merlian returns the right item with evidence + actions

## What we ship in v1 (must-have)
- Local libraries (add/remove folders), incremental indexing, dedupe
- Hybrid retrieval (OCR + visual embeddings) with screenshot-first ranking
- “Personal gallery” views that make messy libraries feel curated
- Explainability: OCR preview + (later) text-region highlight overlay
- Trust UX: clear privacy statement, data locations, reset/forget

## What we do NOT ship in v1
- Accounts, sharing, teams
- Cloud upload/sync
- Public discovery / Pinterest-like network
- “Chat with your photos” as the primary interface

## Success metric (v1)
A new user finds **5–10 previously hard-to-find screenshots/images** in <3 minutes and says they’d pay to have this every day.

## Positioning (early)
**“Spotlight for screenshots, but private and evidence-based.”**

## Pricing hypothesis
Individual subscription, tentatively **$8–15/mo**, justified by repeated time savings + reduced stress in high-pressure moments.
