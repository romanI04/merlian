# STATUS — Merlian

## Current goal
2-week sprint to validate a local-first visual memory search product.

## Today
- Repo scaffold created
- README written with plan + blockers + GitHub workflow
- Imported upstream Dispict into `dispict/` (git subtree, squashed)
- Verified Dispict frontend runs locally

## Next step
- Draft MVP spec for the real local-first product (folder indexing pipeline + stack decision)
- Decide architecture approach (Tauri/Electron + local engine)
- Start thin-slice CLI prototype (index/search) if time permits

## Blockers
- Confirm dataset / image usage terms if we use Harvard demo data.

## Verification checklist
- [x] Dispict frontend runs locally
- [ ] Simple query returns results (requires live backend via Modal)
- [ ] Clear attribution displayed

## Local run (Dispict)
```bash
cd ~/clawd/projects/merlian/dispict
npm install
npm run dev
# open http://127.0.0.1:5173
```
