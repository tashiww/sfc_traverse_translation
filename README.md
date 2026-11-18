# Traverse: Starlight & Prairie — English Translation Project

English translation and Variable-Width Font (VWF) engine implementation for **Traverse: Starlight & Prairie** (トラバース スターライト&プレーリー) for the Super Nintendo Entertainment System (SNES).

* **Target Architecture:** SNES HiROM FastROM (4 MB)
* **Clean ROM Checksum:** CRC32 `739D115C`, SHA1 `5639BF450D268EFE486B2A8C1AE930CD18C3B3BE`
* **Clean Base File:** `rom/Traverse - Starlight & Prairie (Japan).sfc`
* **Git Author Convention:** `tashiww <moetashi@gmail.com>`

---

## 1. Quick Start & Environment Setup

### System Prerequisites
* **OS:** Linux (Ubuntu 20.04+, Debian 11+) or Windows WSL2.
* **Python:** Python 3.10+
* **Dependencies:** Install required Python packages:
  ```bash
  pip install -r requirements.txt
  ```
  *(Only `pillow` and `numpy` are required).*

### Tool Permissions
Ensure bundled ELF assembler and patcher binaries have executable permissions:
```bash
chmod +x bin/asar bin/flips
```

### Base ROM Placement
Ensure the clean Japanese ROM is placed at:
```
rom/Traverse - Starlight & Prairie (Japan).sfc
```

### Building the ROM
Run the automated 5-step build script:
```bash
python3 build.py
```
This performs:
1. Verification of the clean ROM CRC32.
2. Creation of a fresh working copy at `build/traverse_en.sfc`.
3. Assembling 65816 assembly patches via Asar (`asm/main.asm` -> Bank `$CA` VWF engine, redirect tables, font replacements).
4. Inserting script translations from `translations/*.txt` into Bank `$C1`, Bank `$F3`, Bank `$DB`, etc.
5. Recalculating the SNES HiROM checksum and complement.

Output ROM is generated at `build/traverse_en.sfc`.

---

## 2. Headless SNES Emulation & Automated Testing

The repo includes a zero-dependency headless SNES test harness ([tools/headless_snes.py](tools/headless_snes.py)) powered by `snes9x_libretro.so` via Python `ctypes`.

* **No X11 / Display Server Required:** Runs in pure headless Linux/WSL2 and SSH terminals.
* **High Performance:** Executes at ~2,500+ FPS on modern CPUs.
* **Direct WRAM / VRAM Inspection:** Allows inspecting internal game RAM variables in real time.
* **Image Capture:** Captures exact 256x224 RGB frames as Pillow images.

### Running a Test Script
```python
from tools.headless_snes import HeadlessSNES

emu = HeadlessSNES("bin/emu/snes9x_libretro.so")
emu.load_game("build/traverse_en.sfc")

# Advance frames and send joypad inputs
for frame in range(120):
    emu.set_buttons(["START"] if frame % 20 < 10 else [])
    emu.step_frame()

# Inspect WRAM
wram = emu.get_wram()
cursor_pos = wram[0x009B]

# Capture and save a screenshot
img = emu.get_image()
img.save("test_screen.png")
```

---

## 3. LAN Rsync to Another Machine

To synchronize this repository to another local PC while **keeping** the base ROM and the headless emulator core, but **skipping** large downloads, temp frame captures, and scratch states:

```bash
rsync -avPh \
  --include='rom/***' \
  --include='bin/emu/' \
  --include='bin/emu/snes9x_libretro.so' \
  --include='bin/emu/snes9x_libretro.dll' \
  --exclude='bin/emu/*' \
  --filter=':- .gitignore' \
  ./ user@<REMOTE_IP>:/path/to/traverse/
```

*(Transfers ~16 MB total instead of ~350 MB).*

---

## 4. Repository Structure

```
traverse/
├── asm/                     # 65816 assembly source code
│   ├── main.asm             # Master patch entry point (Asar)
│   ├── vwf/                 # Variable-Width Font assembly engine & font data
│   │   ├── vwf.asm          # Proportional VWF renderer for Bank $CA
│   │   ├── font_bank_d3.bin # Universal 16x16 English font (replaces Kana)
│   │   ├── vwf_font.bin     # 8x16 2bpp VWF dialogue font
│   │   └── vwf_widths.bin   # Proportional character width table
│   └── disasm/              # Disassembled reference subroutines from native ROM
├── bin/                     # Native tooling binaries
│   ├── asar                 # 65816 assembler binary
│   ├── flips                # BPS/IPS patch creation binary
│   └── emu/                 # (Gitignored) Emulator binaries
│       ├── snes9x_libretro.so  # Linux headless emulation core
│       └── snes9x_libretro.dll # Windows headless emulation core
├── docs/                    # Technical documentation & architecture references
│   ├── architecture_and_design_decisions.md  # Master system architecture
│   ├── dialogue_engine.md   # Cutscene & dialogue control code mechanics
│   └── memory_map.md        # WRAM, VRAM, and ROM memory layout
├── rom/                     # (Gitignored) Clean base ROM directory
├── tables/                  # Codepage mapping tables (.tbl)
│   ├── en_tbl.tbl           # Unified Master English Table
│   ├── ja_tbl.tbl           # Native Japanese table
│   └── prologue.tbl         # Prologue cutscene table
├── tools/                   # Build and automation scripts
│   ├── build_font_bank_d3.py # Generates Bank D3 16x16 font binary
│   ├── build_font_vwf.py    # Generates 8x16 VWF font binary & widths
│   ├── dumper.py            # Script text extractor
│   ├── headless_snes.py     # Headless emulator Python runner
│   └── inserter.py          # Script and table injector with Greenfield Bank $CA pool
├── translations/            # Human-editable translation files
│   ├── dialogue_bank_F3.txt # Bank F3 in-game dialogue
│   ├── dialogue_prologue.txt# Prologue Goddess surveys & intro scene
│   ├── location_names.txt   # World map location banners
│   ├── pet_names.txt        # 32 pet name suggestions + default Boancho
│   ├── pet_species.txt      # 8 pet species
│   └── pet_colors.txt       # 12 pet colors
├── build.py                 # Automated 1-click ROM builder
├── requirements.txt         # Python dependencies
└── .gitignore               # Ignored build artifacts, scratch files, and dumps
```

---

## 5. Guidelines for AI Assistants & Antigravity

When working in this repository with Antigravity:

1. **Commit Author:** Always commit using author:
   ```bash
   git commit --author="tashiww <moetashi@gmail.com>" -m "..."
   ```
2. **Never Hand-Patch Output ROMs:** Always make changes in `asm/`, `tools/`, or `translations/` and execute `python3 build.py`.
3. **Prefer Python Pre-Parsing Over Complex ASM:** Avoid brittle assembly patches where Python tooling (`inserter.py`, `smart_wrap_text`, table lookups) can format or pre-calculate data.
4. **Dialogue Line & Box Limits:**
   * Proportional dialogue box width limit is **216 pixels**.
   * Dynamic variables `[protag]`, `[sub]`, and `[pet]` are budgeted equally at **64 pixels** (8 characters × 8px worst-case).
   * Manual line breaks in `translations/dialogue_*.txt` are respected; `inserter.py` automatically word-wraps lines exceeding 216 px.
5. **Headless Verification:** Always write quick Python verification scripts utilizing `HeadlessSNES` from [tools/headless_snes.py](tools/headless_snes.py) to confirm visual rendering before reporting completion.
