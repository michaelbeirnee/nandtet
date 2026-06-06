#!/usr/bin/env python3
"""Regression tests for the full nand2tetris toolchain and emulators.

Runnable two ways:
    python3 tests/test_toolchain.py     # built-in runner, no dependencies
    pytest tests/test_toolchain.py      # if pytest is installed
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emulator import CPU, load_hack, SCREEN_BASE, SCREEN_WORDS
from tools.vmemu import VMEmulator, load_dir


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


assembler = _load('assembler', 'projects/06/assembler.py')
vmtrans   = _load('vmtrans',   'projects/07/vm.py')
compiler  = _load('compiler',  'projects/10/compiler.py')


# ── assembler + CPU (projects 04/05) ────────────────────────────────────────────

def test_mult_program():
    cpu = CPU(load_hack(ROOT / 'projects/04/Mult.hack'))
    cpu.poke(0, 9); cpu.poke(1, 8)
    cpu.run(max_cycles=10_000)
    assert cpu.peek(2) == 72, f'9*8 should be 72, got {cpu.peek(2)}'


def test_fill_program():
    rom = load_hack(ROOT / 'projects/04/Fill.hack')
    cpu = CPU(rom)
    cpu.set_key(88)
    cpu.run(max_cycles=400_000)
    assert all(cpu.peek(SCREEN_BASE + i) == 0xFFFF for i in range(SCREEN_WORDS))
    cpu.set_key(0)
    cpu.run(max_cycles=400_000)
    assert all(cpu.peek(SCREEN_BASE + i) == 0 for i in range(SCREEN_WORDS))


def test_assembler_symbol_resolution():
    asm = '@i\nD=A\n@sum\nM=D\n(LOOP)\n@LOOP\n0;JMP\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 't.asm'; p.write_text(asm)
        out = assembler.assemble(p).split()
    assert out[0] == format(16, '016b')      # first variable @i → RAM 16
    assert out[2] == format(17, '016b')      # @sum → RAM 17
    assert out[4] == format(4, '016b')       # @LOOP label → instruction 4


# ── VM translator + assembler + CPU (projects 07/08) ────────────────────────────

def test_vm_arithmetic_through_cpu():
    vm = 'push constant 7\npush constant 6\nadd\npush constant 1\nsub\npop temp 0\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'T.vm'; p.write_text(vm)
        asm = vmtrans.translate(p)               # single file → no bootstrap
        hack = assembler.assemble(asm)
        rom = [int(x, 2) for x in hack.split()]
    cpu = CPU(rom)
    cpu.poke(0, 256)                              # init SP by hand (no bootstrap)
    cpu.run(max_cycles=1000)
    assert cpu.peek(5) == 12, f'(7+6)-1 should be 12, got {cpu.peek(5)}'   # temp 0 = R5


# ── compiler + VM emulator (projects 10/11) ─────────────────────────────────────

def test_compiler_loop_sum():
    jack = '''class Sys {
        static int result;
        function void init() {
            var int i, s;
            let s = 0; let i = 1;
            while (i < 11) { let s = s + i; let i = i + 1; }
            let result = s;
            return;
        }
    }'''
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'Sys.jack'; p.write_text(jack)
        compiler.compile_file(p)
        emu = VMEmulator(load_dir(d))
        emu.run(100_000)
    assert emu.ram[emu.statics[('Sys', 0)]] == 55, 'sum 1..10 should be 55'


def test_vmemu_function_call():
    vm = '''function Sys.init 0
    push constant 4
    call Sys.sq 1
    pop static 0
    return
    function Sys.sq 0
    push argument 0
    push argument 0
    call Sys.mul 2
    return
    function Sys.mul 0
    push argument 0
    push argument 1
    add
    return
    '''
    # (mul here is really add, just exercising nested calls/returns)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'Sys.vm'; p.write_text(vm)
        emu = VMEmulator(load_dir(d))
        emu.run(10_000)
    assert emu.ram[emu.statics[('Sys', 0)]] == 8, 'sq(4) via add should be 8'


# ── full stack: build Tetris and boot it on the VM emulator ─────────────────────

def test_tetris_builds_and_boots():
    build = _load('build', 'tools/build.py')
    with tempfile.TemporaryDirectory() as d:
        build.build(ROOT / 'projects/09', Path(d), 'Tetris')
        emu = VMEmulator(load_dir(Path(d) / 'build'))
        emu.run(3_000_000)
    lit = sum(p for row in emu.screen_rows() for p in row)
    assert lit > 400, f'Tetris should draw the playfield, only {lit} pixels lit'


# ── runner ──────────────────────────────────────────────────────────────────────

def _main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            failed += 1
            print(f'  FAIL  {t.__name__}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(_main())
