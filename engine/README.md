# Merlian engine (thin-slice)

This folder contains a minimal CLI prototype to validate the local-first core:

- index a folder of images (compute CLIP embeddings locally)
- search by text and print top matches

## Setup

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Index

```bash
source .venv/bin/activate
python merlian.py index ~/Desktop --device cpu
```

## Search

```bash
source .venv/bin/activate
python merlian.py search "red sneaker" --k 10 --device cpu
```

## Reset

```bash
source .venv/bin/activate
python merlian.py reset
```

### Notes
- Index artifacts are stored under `engine/.merlian/` (repo-local for now).
- This is not optimized; it’s a validation harness.
