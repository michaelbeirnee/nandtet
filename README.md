# nandtet — NAND to Tetris

A complete [nand2tetris](https://www.nand2tetris.org/) build: a 16-bit computer
specified from NAND gates up, the full software toolchain that targets it
(assembler, VM translator, Jack compiler, OS library), and two emulators that
actually run the result — culminating in a playable **Tetris**.

```
Jack source ──compiler──▶ VM code ──translator──▶ Hack assembly ──assembler──▶ Hack binary
                            │                                                      │
                            ▼                                                      ▼
                      VM emulator                                           CPU emulator
                   (plays Tetris, no                                    (runs .hack on the
                    32K ROM ceiling)                                     gate-level machine)
```

## Quick start

```bash
make test        # run the full regression suite (no third-party deps)
make snapshot    # build Tetris and render a headless PNG to dist/tetris.png
make play        # build Tetris and play it in a window  (needs: pip install pygame)
```

## Layout

The `projects/` tree mirrors the nand2tetris course. Projects 08 and 11 are
folded into 07 and 10 respectively (the same tools cover both halves).

| Project | What it is | Contents |
|--------:|------------|----------|
| `01` | Boolean logic | And, Or, Not, Mux, DMux … (`.hdl`) |
| `02` | Arithmetic | HalfAdder, FullAdder, Add16, Inc16, ALU |
| `03` | Sequential logic | Bit, Register, RAM8…RAM16K, PC |
| `04` | Machine language | `Mult.asm`, `Fill.asm` (+ assembled `.hack`) |
| `05` | Computer architecture | CPU, Memory, Computer (`.hdl`) |
| `06` | Assembler | `assembler.py`: `.asm → .hack` |
| `07`/`08` | VM translator | `vm.py`: `.vm → .asm` (arithmetic, memory, flow, functions) |
| `09` | High-level program | `Tetris.jack`, `Main.jack` |
| `10`/`11` | Jack compiler | `compiler.py`: `.jack → .vm` (tokenize, parse, codegen) |
| `12` | OS library | Math, Memory, Screen, Output, Keyboard, String, Array, Sys |

The cross-cutting tools added to drive the whole thing live in `tools/`:

| File | Role |
|------|------|
| `tools/build.py`  | end-to-end pipeline: Jack → VM → asm → Hack binary |
| `tools/emulator.py` | Hack **CPU** emulator — executes a `.hack` image on the gate-level machine |
| `tools/vmemu.py`  | Hack **VM** emulator — executes `.vm` bytecode directly |
| `tools/play.py`   | pygame window (or headless PNG snapshot) over either emulator |

## Building and running Tetris

```bash
python3 tools/build.py                       # → dist/Tetris.hack (+ dist/build/*.vm)
python3 tools/play.py dist/build             # play (pygame)
python3 tools/play.py dist/build --snapshot dist/shot.png --warmup 14000000 --key 132
```

Controls: **← →** move, **↑** rotate, **↓** soft drop, **space** hard drop.

## Running smaller programs on the real CPU

The CPU emulator runs any assembled `.hack` image on the machine defined in
projects 01–05:

```bash
python3 tools/emulator.py projects/04/Mult.hack --dump 2   # R2 = R0*R1
python3 tools/emulator.py projects/04/Fill.hack --screen   # blackens on keypress
```

## Why Tetris runs on the VM emulator, not the CPU

The Hack CPU addresses ROM with the 15-bit value in an `@` (A-)instruction, so
**code must fit in 32 768 instructions**. The OS library plus Tetris compiles to
~52 000 assembly instructions; any label above address 32 767 sets bit 15 of the
`@` word, which the CPU then decodes as a *C-instruction* instead of a jump — so
the image cannot run on the literal 32K machine.

This is exactly why the nand2tetris course runs Project-9 games on the supplied
**VM Emulator**: `tools/vmemu.py` executes the stack machine directly, with no
ROM ceiling, using the same RAM/screen/keyboard memory map as the CPU. The CPU
emulator and assembler are exercised end-to-end by the smaller project-04/05
programs (and by the regression tests). `tools/build.py` still emits the full
`.hack` and prints a note when an image exceeds the 32K limit.

## Tests

`tests/test_toolchain.py` covers every layer — assembler, CPU emulator, VM
translator, Jack compiler, VM emulator, and a full Tetris build-and-boot — and
runs with the standard library alone (also works under `pytest`).
