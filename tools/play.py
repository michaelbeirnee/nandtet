#!/usr/bin/env python3
"""Interactive front-end for the Hack machine.

Runs either a compiled game (.vm directory, via the VM emulator) or a .hack
image (via the CPU emulator), renders the 512x256 Hack screen in a window, and
forwards key presses as Hack keyboard scan codes.

    python3 tools/play.py dist/build           # play Tetris (compiled .vm)
    python3 tools/play.py projects/04/Fill.hack

The interactive window needs `pygame` (pip install pygame).  Without a display
you can still render a snapshot headlessly:

    python3 tools/play.py dist/build --snapshot shot.png --warmup 3000000
"""

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.emulator import CPU, load_hack, SCREEN_W, SCREEN_H

# ── Hack keyboard scan codes ────────────────────────────────────────────────────
# Special keys per the Hack spec; printable characters map to their ASCII code.
SPECIAL = {
    'RETURN': 128, 'BACKSPACE': 129, 'LEFT': 130, 'UP': 131, 'RIGHT': 132,
    'DOWN': 133, 'HOME': 134, 'END': 135, 'PAGEUP': 136, 'PAGEDOWN': 137,
    'INSERT': 138, 'DELETE': 139, 'ESCAPE': 140,
}

# ── screen → RGB framebuffer (pure, no dependencies) ─────────────────────────────

_BLACK = b'\x00\x00\x00'
_WHITE = b'\xff\xff\xff'
_LUT = None


def _lut():
    """word → 16 RGB pixels (bit 0 = leftmost, 1 = black), built once."""
    global _LUT
    if _LUT is None:
        _LUT = [b''.join(_BLACK if (w >> b) & 1 else _WHITE for b in range(16))
                for w in range(65536)]
    return _LUT


def framebuffer(emu) -> bytes:
    """Render the emulator's screen memory to a 512x256 RGB byte buffer."""
    lut = _lut()
    base = 0x4000
    ram = emu.ram
    rows = []
    for r in range(SCREEN_H):
        off = base + r * 32
        rows.append(b''.join(lut[ram[off + w]] for w in range(32)))
    return b''.join(rows)


def write_png(path, rgb: bytes, w: int = SCREEN_W, h: int = SCREEN_H):
    """Minimal PNG writer (stdlib only) so snapshots are viewable anywhere."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)                       # filter type 0 for this scanline
        raw += rgb[y * w * 3:(y + 1) * w * 3]

    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)   # 8-bit RGB
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
           + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))
    Path(path).write_bytes(png)


# ── emulator construction ───────────────────────────────────────────────────────

def make_emu(target: str):
    """Return (emulator, steps_per_frame) for a .hack file or .vm directory."""
    p = Path(target)
    if p.is_file() and p.suffix == '.hack':
        return CPU(load_hack(p)), 80_000        # ~10 Hack instrs per VM op
    from tools.vmemu import VMEmulator, load_dir
    return VMEmulator(load_dir(p)), 8_000


# ── headless snapshot ───────────────────────────────────────────────────────────

def snapshot(target: str, out: str, warmup: int, key: int = 0):
    emu, _ = make_emu(target)
    if key:
        # run, then hold a key, to capture a responsive frame
        emu.run(warmup // 2)
        emu.set_key(key)
        emu.run(warmup // 2)
    else:
        emu.run(warmup)
    write_png(out, framebuffer(emu))
    lit = sum(p for row in emu.screen_rows() for p in row)
    print(f'wrote {out}  (lit pixels: {lit})')


# ── interactive window (pygame) ─────────────────────────────────────────────────

def play(target: str, scale: int, fps: int):
    try:
        import pygame
    except ImportError:
        sys.exit('pygame is required for interactive play:  pip install pygame\n'
                 'Or render a snapshot headlessly with --snapshot out.png')

    keymap = {getattr(pygame, f'K_{n}'): code for n, code in SPECIAL.items()}
    emu, steps = make_emu(target)

    pygame.init()
    win = pygame.display.set_mode((SCREEN_W * scale, SCREEN_H * scale))
    pygame.display.set_caption(f'Hack — {Path(target).name}')
    clock = pygame.time.Clock()
    cur_key = 0
    running = True

    def hack_code(event):
        if event.key in keymap:
            return keymap[event.key]
        ch = event.unicode
        return ord(ch) if ch and 32 <= ord(ch) < 127 else 0

    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE and not cur_key:
                    pass
                cur_key = hack_code(e) or cur_key
            elif e.type == pygame.KEYUP:
                cur_key = 0
        emu.set_key(cur_key)
        emu.run(steps)
        if getattr(emu, 'halted', False):
            running = False

        surf = pygame.image.frombuffer(framebuffer(emu), (SCREEN_W, SCREEN_H), 'RGB')
        pygame.transform.scale(surf, win.get_size(), win)
        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Play a Hack program in a window.')
    ap.add_argument('target', help='.hack image or directory of .vm files')
    ap.add_argument('--scale', type=int, default=2, help='pixel scale (default 2)')
    ap.add_argument('--fps', type=int, default=30, help='target frames/sec')
    ap.add_argument('--snapshot', metavar='PNG',
                    help='headless: run then write a PNG screenshot (no pygame)')
    ap.add_argument('--warmup', type=int, default=3_000_000,
                    help='steps to run before snapshot')
    ap.add_argument('--key', type=int, default=0,
                    help='hold this scan code during the second half of warmup')
    args = ap.parse_args()

    if args.snapshot:
        snapshot(args.target, args.snapshot, args.warmup, args.key)
    else:
        play(args.target, args.scale, args.fps)


if __name__ == '__main__':
    main()
