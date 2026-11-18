# Antigravity Agent Guidelines — Traverse: Starlight & Prairie

Welcome to the Traverse translation repository. This file provides immediate context and rules for AI agents running in this workspace.

## 1. Project Overview
* **Game:** *Traverse: Starlight & Prairie* (SFC / SNES)
* **Architecture:** HiROM FastROM 4MB
* **Base ROM:** `rom/Traverse - Starlight & Prairie (Japan).sfc` (CRC32: `739D115C`)
* **Output ROM:** `build/traverse_en.sfc`
* **Git Author Convention:** `tashiww <moetashi@gmail.com>`

## 2. Environment & Build Commands
* **Python packages:** `pip install -r requirements.txt` (`pillow`, `numpy`)
* **Asar & Flips:** Bundled in `bin/asar` and `bin/flips` (`chmod +x bin/asar bin/flips`)
* **Build Command:**
  ```bash
  python3 build.py
  ```
  *(Always build via `build.py`; never edit `build/traverse_en.sfc` directly).*
* **Headless SNES Emulator:**
  `tools/headless_snes.py` loads `bin/emu/snes9x_libretro.so` via `ctypes`.
  Run headless verification scripts in Python without needing X11.

## 3. Core Architecture Rules
* **Bank $D3 Universal 16x16 Font:** Japanese Kana glyphs were replaced with 16x16 English letters (`asm/vwf/font_bank_d3.bin`). Any fixed-width banner or menu indexed here renders English.
* **Bank $CA Dialogue VWF Engine:** Proportional Variable-Width Font engine hooks at `$DC:CAA1`. Strings are relocated to Bank `$CA` via `StringRedirectTable` at `$CA:7000`.
* **Dialogue Width Budget:** Max width per line is **216 pixels**.
* **Dynamic Character Name Budget:** `[protag]`, `[sub]`, and `[pet]` are each budgeted at **64 pixels** (8 characters × 8px worst-case).
* **Translations:** In `translations/*.txt`. Lines can be broken manually or auto-wrapped by `tools/inserter.py`.
* **Pet Data:** Fixed in-place tables in Bank `$DB` (`pet_names.txt`, `pet_colors.txt`, `pet_species.txt`).

## 4. Documentation References
* Detailed architecture: [docs/architecture_and_design_decisions.md](docs/architecture_and_design_decisions.md)
* Dialogue control codes: [docs/dialogue_engine.md](docs/dialogue_engine.md)
* Memory map: [docs/memory_map.md](docs/memory_map.md)
