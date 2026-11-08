#!/usr/bin/env python3
"""
Headless SNES emulator runner using snes9x_libretro.so
Allows automated scripting, button mashing, and screenshot capture in pure headless Linux/WSL2.
"""

import sys
import os
import time
import ctypes
import numpy as np
from PIL import Image

LIBRETRO_CORE = "bin/emu/snes9x_libretro.so"
ROM_PATH = "build/traverse_en.sfc"
OUTPUT_DIR = "problems/headless_captures"

# Joypad button mappings
RETRO_DEVICE_JOYPAD = 1
BUTTONS = {
    "B": 0,
    "Y": 1,
    "SELECT": 2,
    "START": 3,
    "UP": 4,
    "DOWN": 5,
    "LEFT": 6,
    "RIGHT": 7,
    "A": 8,
    "X": 9,
    "L": 10,
    "R": 11,
}

ENV_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
VIDEO_REFRESH = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t)
AUDIO_SAMPLE = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
AUDIO_SAMPLE_BATCH = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t)
INPUT_POLL = ctypes.CFUNCTYPE(None)
INPUT_STATE = ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint)

class RetroGameInfo(ctypes.Structure):
    _fields_ = [
        ("path", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("meta", ctypes.c_char_p),
    ]

class HeadlessSNES:
    def __init__(self, core_path=LIBRETRO_CORE):
        self.core = ctypes.CDLL(core_path)
        self.core.retro_get_memory_data.restype = ctypes.c_void_p
        self.core.retro_get_memory_data.argtypes = [ctypes.c_uint]
        self.core.retro_get_memory_size.restype = ctypes.c_size_t
        self.core.retro_get_memory_size.argtypes = [ctypes.c_uint]

        self.current_buttons = set()
        self.last_frame_bytes = None
        self.width = 0
        self.height = 0
        self.pitch = 0
        self.frame_num = 0

        # Retain C callback references to prevent garbage collection
        self._c_env_cb = ENV_CALLBACK(self._env_cb)
        self._c_video_cb = VIDEO_REFRESH(self._video_cb)
        self._c_audio_cb = AUDIO_SAMPLE(lambda l, r: None)
        self._c_audio_batch_cb = AUDIO_SAMPLE_BATCH(lambda d, f: f)
        self._c_input_poll_cb = INPUT_POLL(lambda: None)
        self._c_input_state_cb = INPUT_STATE(self._input_state_cb)

        self.core.retro_set_environment(self._c_env_cb)
        self.core.retro_set_video_refresh(self._c_video_cb)
        self.core.retro_set_audio_sample(self._c_audio_cb)
        self.core.retro_set_audio_sample_batch(self._c_audio_batch_cb)
        self.core.retro_set_input_poll(self._c_input_poll_cb)
        self.core.retro_set_input_state(self._c_input_state_cb)

        self.core.retro_init()

    def _env_cb(self, cmd, data):
        if cmd == 10:  # RETRO_ENVIRONMENT_SET_PIXEL_FORMAT
            return True
        return False

    def _video_cb(self, data, width, height, pitch):
        if data and width > 0 and height > 0:
            self.last_frame_bytes = bytes(ctypes.string_at(data, height * pitch))
            self.width = width
            self.height = height
            self.pitch = pitch

    def _input_state_cb(self, port, device, index, btn_id):
        if port == 0 and device == RETRO_DEVICE_JOYPAD:
            return 1 if btn_id in self.current_buttons else 0
        return 0

    def load_game(self, rom_path):
        with open(rom_path, "rb") as f:
            self.rom_data = f.read()

        game_info = RetroGameInfo(
            path=rom_path.encode("utf-8"),
            data=ctypes.cast(ctypes.c_char_p(self.rom_data), ctypes.c_void_p),
            size=len(self.rom_data),
            meta=None,
        )
        ok = self.core.retro_load_game(ctypes.byref(game_info))
        if not ok:
            raise RuntimeError(f"Failed to load ROM: {rom_path}")
        print(f"Loaded ROM: {rom_path} ({len(self.rom_data)} bytes)")

    def set_buttons(self, button_list):
        self.current_buttons = set()
        for b in button_list:
            if b in BUTTONS:
                self.current_buttons.add(BUTTONS[b])

    def step_frame(self):
        self.core.retro_run()
        self.frame_num += 1

    def step_frames(self, count):
        for _ in range(count):
            self.step_frame()

    def get_image(self):
        if not self.last_frame_bytes:
            return None
        arr = np.frombuffer(self.last_frame_bytes, dtype=np.uint16).reshape(
            (self.height, self.pitch // 2)
        )[:, : self.width]
        r = (((arr >> 11) & 0x1F) * 255 // 31).astype(np.uint8)
        g = (((arr >> 5) & 0x3F) * 255 // 63).astype(np.uint8)
        b = ((arr & 0x1F) * 255 // 31).astype(np.uint8)
        rgb = np.stack([r, g, b], axis=-1)
        return Image.fromarray(rgb)

    def save_screenshot(self, filename):
        img = self.get_image()
        if img:
            os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
            img.save(filename)
            return True
        return False

    def get_wram(self):
        ptr = self.core.retro_get_memory_data(2)  # RETRO_MEMORY_SYSTEM_RAM
        size = self.core.retro_get_memory_size(2)
        if ptr and size:
            return bytes(ctypes.string_at(ptr, size))
        return None

    def close(self):
        self.core.retro_unload_game()
        self.core.retro_deinit()

def run_sequence():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    emu = HeadlessSNES()
    emu.load_game(ROM_PATH)

    print("Beginning automated emulation sequence...")
    start_time = time.time()

    # Plan:
    # 1. 0..300: Mash START to skip logos / intro cinematics
    # 2. 300..600: Mash START to start new game
    # 3. 600..1200: Mash START (to confirm default name) and mash A
    # 4. 1200..3000: Mash A to advance through dialogue

    last_saved_img = None
    saved_count = 0

    for f in range(4000):
        # Determine button presses
        cycle = f % 16
        is_press = (cycle < 8)

        if f < 500:
            # Mash START to skip logos
            emu.set_buttons(["START"] if is_press else [])
        elif f < 800:
            # Mash START or A to start game
            btn = "START" if (f // 60) % 2 == 0 else "A"
            emu.set_buttons([btn] if is_press else [])
        elif f < 1200:
            # On naming screen: press START to confirm default name "GANT"!
            emu.set_buttons(["START"] if is_press else [])
        else:
            # Dialogue reading: mash A or B to advance dialogue
            btn = "A" if (f % 30 < 15) else "B"
            emu.set_buttons([btn] if is_press else [])

        emu.step_frame()

        # Capture screenshot periodically
        if f > 0 and (f % 100 == 0 or f in (1250, 1350, 1450, 1550, 1650, 1750, 1850, 2050, 2250, 2500, 3000, 3500, 3999)):
            img = emu.get_image()
            if img:
                arr = np.array(img)
                # Check if non-blank
                if arr.std() > 5:  # Not completely black or solid color
                    out_path = f"{OUTPUT_DIR}/frame_{f:05d}.png"
                    img.save(out_path)
                    saved_count += 1
                    print(f"[{f:05d}] Saved {out_path} (mean={arr.mean():.1f}, std={arr.std():.1f})")

    elapsed = time.time() - start_time
    fps = emu.frame_num / max(elapsed, 0.001)
    print(f"Emulation finished: {emu.frame_num} frames in {elapsed:.2f}s ({fps:.1f} fps), {saved_count} screenshots saved.")
    emu.close()

if __name__ == "__main__":
    run_sequence()
