#!/usr/bin/env python3
"""Hack CPU emulator — executes a .hack image (the machine built in projects 01-05).

Faithful to the Hack platform:
  * 16-bit words, two's-complement arithmetic.
  * Registers A, D and program counter PC.
  * Memory map:  0x0000-0x3FFF  data (RAM16K)
                 0x4000-0x5FFF  screen  (512x256 monochrome, 8K words)
                 0x6000         keyboard (read-only scan code)

The real Hack ROM is 32K (15-bit addresses).  This emulator does not enforce
that ceiling so it can also run images larger than 32K (e.g. the full OS + a
game); pass strict_rom=True to emulate the hardware limit exactly.
"""

from pathlib import Path

WORD = 0xFFFF
SCREEN_BASE = 0x4000          # 16384
SCREEN_WORDS = 0x2000         # 8192  (256 rows x 32 words)
KBD = 0x6000                  # 24576
SCREEN_W, SCREEN_H = 512, 256


def _signed(v: int) -> int:
    """Interpret a 16-bit word as signed two's complement."""
    return v - 0x10000 if v & 0x8000 else v


def _alu(x: int, y: int, zx, nx, zy, ny, f, no) -> int:
    """The Hack ALU: six control bits over two 16-bit inputs."""
    if zx: x = 0
    if nx: x = ~x
    if zy: y = 0
    if ny: y = ~y
    out = (x + y) if f else (x & y)
    if no: out = ~out
    return out & WORD


class CPU:
    def __init__(self, rom, strict_rom: bool = False):
        if strict_rom and len(rom) > 0x8000:
            raise ValueError(f'image of {len(rom)} words exceeds 32K Hack ROM')
        self.rom = rom
        self.ram = [0] * 0x6001          # through the keyboard word
        self.a = self.d = self.pc = 0
        self.cycles = 0

    # ── memory helpers ─────────────────────────────────────────────────────────

    def peek(self, addr: int) -> int:
        return self.ram[addr]

    def poke(self, addr: int, value: int):
        self.ram[addr] = value & WORD

    def set_key(self, code: int):
        """Set the keyboard scan code (0 = no key)."""
        self.ram[KBD] = code & WORD

    # ── execution ──────────────────────────────────────────────────────────────

    def step(self):
        if self.pc >= len(self.rom):
            return False
        instr = self.rom[self.pc]
        self.cycles += 1

        if not (instr & 0x8000):              # @value  (A-instruction)
            self.a = instr & WORD
            self.pc += 1
            return True

        # C-instruction: 111 a c1c2c3c4c5c6 d1d2d3 j1j2j3
        a  = (instr >> 12) & 1
        c  = (instr >> 6) & 0x3F
        d  = (instr >> 3) & 0x7
        j  = instr & 0x7

        y = self.ram[self.a] if a else self.a
        out = _alu(self.d, y,
                   c >> 5 & 1, c >> 4 & 1, c >> 3 & 1,
                   c >> 2 & 1, c >> 1 & 1, c & 1)

        if d & 0b001:                          # M = out  (uses current A)
            self.poke(self.a, out)
        if d & 0b010:                          # D = out
            self.d = out
        if d & 0b100:                          # A = out
            self.a = out

        s = _signed(out)
        jump = ((j & 0b100 and s < 0) or
                (j & 0b010 and s == 0) or
                (j & 0b001 and s > 0))
        self.pc = self.a if jump else self.pc + 1
        return True

    def run(self, max_cycles: int = None):
        """Run until the PC leaves the ROM or max_cycles is reached."""
        n = 0
        while self.step():
            n += 1
            if max_cycles is not None and n >= max_cycles:
                break
        return n

    # ── screen ─────────────────────────────────────────────────────────────────

    def screen_rows(self):
        """Yield 256 rows, each a list of 512 ints (0/1), MSB-of-word = leftmost."""
        for r in range(SCREEN_H):
            row = []
            base = SCREEN_BASE + r * 32
            for w in range(32):
                word = self.ram[base + w]
                for bit in range(16):           # Hack draws bit 0 as the left pixel
                    row.append((word >> bit) & 1)
            yield row


def load_hack(path) -> list:
    """Read a .hack file (one 16-bit binary string per line) into a word list."""
    text = Path(path).read_text().split()
    return [int(line, 2) for line in text if line]


# ── ascii rendering (for headless inspection / terminal play) ────────────────────

def render_ascii(cpu: CPU, cols: int = 64, rows: int = 32) -> str:
    """Downsample the screen to an ASCII block grid for terminal display."""
    pix = list(cpu.screen_rows())
    cw, ch = SCREEN_W // cols, SCREEN_H // rows
    out = []
    for ry in range(rows):
        line = []
        for rx in range(cols):
            on = any(pix[ry * ch + dy][rx * cw + dx]
                     for dy in range(ch) for dx in range(cw))
            line.append('█' if on else ' ')
        out.append(''.join(line))
    return '\n'.join(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Run a .hack image on the Hack CPU.')
    ap.add_argument('image', help='path to .hack file')
    ap.add_argument('-c', '--cycles', type=int, default=1_000_000,
                    help='max cycles to execute (default 1e6)')
    ap.add_argument('--strict-rom', action='store_true',
                    help='enforce the 32K Hack ROM limit')
    ap.add_argument('--screen', action='store_true',
                    help='render the screen as ASCII after running')
    ap.add_argument('--dump', metavar='ADDR', type=int, nargs='+',
                    help='print RAM[ADDR] values after running')
    args = ap.parse_args()

    cpu = CPU(load_hack(args.image), strict_rom=args.strict_rom)
    ran = cpu.run(max_cycles=args.cycles)
    print(f'ran {ran} cycles (PC={cpu.pc}, A={cpu.a}, D={cpu.d})')
    if args.dump:
        for addr in args.dump:
            print(f'RAM[{addr}] = {cpu.peek(addr)} ({_signed(cpu.peek(addr))})')
    if args.screen:
        print(render_ascii(cpu))


if __name__ == '__main__':
    main()
