#!/usr/bin/env python3
"""Hack VM emulator — executes .vm bytecode directly (the way nand2tetris runs
Project-9 games).

The full OS library plus a game compiles to more than 32K assembly
instructions, which can't fit in the Hack CPU's 15-bit ROM address space.  So,
exactly like the official nand2tetris VM Emulator, this runs the stack machine
itself rather than the assembled image — no ROM ceiling.

It uses the same flat RAM model and memory map as the CPU (screen at 16384,
keyboard at 24576), so the compiled Screen/Keyboard/Output OS classes drive the
display correctly.  Static segments are allocated per source file from RAM 16
upward, matching the standard VM mapping.
"""

import re
from pathlib import Path

SP, LCL, ARG, THIS, THAT = 0, 1, 2, 3, 4
TEMP_BASE = 5
SCREEN_BASE = 0x4000
SCREEN_WORDS = 0x2000
KBD = 0x6000
SCREEN_W, SCREEN_H = 512, 256
WORD = 0xFFFF

_PTR = {0: THIS, 1: THAT}
_SEG_REG = {'local': LCL, 'argument': ARG, 'this': THIS, 'that': THAT}

def _signed(v):
    return v - 0x10000 if v & 0x8000 else v

class Instr:
    __slots__ = ('op', 'arg1', 'arg2', 'func', 'file')

    def __init__(self, op, arg1, arg2, func, file):
        self.op, self.arg1, self.arg2, self.func, self.file = op, arg1, arg2, func, file

class VMEmulator:
    def __init__(self, vm_files):
        self.ram = [0] * (KBD + 1)
        self.ram[SP] = 256
        self.code = []
        self.functions = {}
        self.labels = {}
        self.statics = {}
        self._next_static = 16
        self.halted = False
        self._load(vm_files)
        self.pc = self.functions.get('Sys.init')
        if self.pc is None:
            raise ValueError('no Sys.init found in VM files')
        self._enter('Sys.init', 0, return_pc=None)

    def _load(self, vm_files):
        cur_func = ''
        for path in vm_files:
            path = Path(path)
            file = path.stem
            for raw in path.read_text().splitlines():
                line = re.sub(r'//.*', '', raw).strip()
                if not line:
                    continue
                p = line.split()
                op = p[0]
                idx = len(self.code)
                if op == 'function':
                    cur_func = p[1]
                    self.functions[p[1]] = idx
                elif op == 'label':
                    self.labels[(cur_func, p[1])] = idx
                a1 = p[1] if len(p) > 1 else None
                a2 = int(p[2]) if len(p) > 2 else None
                self.code.append(Instr(op, a1, a2, cur_func, file))

    def _static_addr(self, file, i):
        key = (file, i)
        if key not in self.statics:
            self.statics[key] = self._next_static
            self._next_static += 1
        return self.statics[key]

    def _push(self, v):
        self.ram[self.ram[SP]] = v & WORD
        self.ram[SP] += 1

    def _pop(self):
        self.ram[SP] -= 1
        return self.ram[self.ram[SP]]

    def _enter(self, name, n_args, return_pc):
        self._push(return_pc if return_pc is not None else 0xFFFF)
        for reg in (LCL, ARG, THIS, THAT):
            self._push(self.ram[reg])
        self.ram[ARG] = self.ram[SP] - 5 - n_args
        self.ram[LCL] = self.ram[SP]
        target = self.functions[name]
        self.pc = target

    def step(self):
        if self.halted or self.pc is None or self.pc >= len(self.code):
            self.halted = True
            return False
        ins = self.code[self.pc]
        op = ins.op
        nxt = self.pc + 1

        if op == 'push':
            self._push(self._load_seg(ins.arg1, ins.arg2, ins.file))
        elif op == 'pop':
            self._store_seg(ins.arg1, ins.arg2, ins.file, self._pop())
        elif op == 'function':
            for _ in range(ins.arg2):
                self._push(0)
        elif op == 'call':
            self._enter(ins.arg1, ins.arg2, return_pc=nxt)
            return True
        elif op == 'return':
            frame = self.ram[LCL]
            ret = self.ram[frame - 5]
            retval = self._pop()
            self.ram[self.ram[ARG]] = retval
            self.ram[SP] = self.ram[ARG] + 1
            self.ram[THAT] = self.ram[frame - 1]
            self.ram[THIS] = self.ram[frame - 2]
            self.ram[ARG] = self.ram[frame - 3]
            self.ram[LCL] = self.ram[frame - 4]
            if ret == 0xFFFF:
                self.halted = True
                return False
            self.pc = ret
            return True
        elif op == 'label':
            pass
        elif op == 'goto':
            self.pc = self.labels[(ins.func, ins.arg1)]
            return True
        elif op == 'if-goto':
            if self._pop() != 0:
                self.pc = self.labels[(ins.func, ins.arg1)]
                return True
        else:
            self._arith(op)

        self.pc = nxt
        return True

    def _load_seg(self, seg, i, file):
        if seg == 'constant':
            return i & WORD
        if seg in _SEG_REG:
            return self.ram[self.ram[_SEG_REG[seg]] + i]
        if seg == 'temp':
            return self.ram[TEMP_BASE + i]
        if seg == 'pointer':
            return self.ram[_PTR[i]]
        if seg == 'static':
            return self.ram[self._static_addr(file, i)]
        raise ValueError(f'bad segment {seg}')

    def _store_seg(self, seg, i, file, val):
        val &= WORD
        if seg in _SEG_REG:
            self.ram[self.ram[_SEG_REG[seg]] + i] = val
        elif seg == 'temp':
            self.ram[TEMP_BASE + i] = val
        elif seg == 'pointer':
            self.ram[_PTR[i]] = val
        elif seg == 'static':
            self.ram[self._static_addr(file, i)] = val
        else:
            raise ValueError(f'bad segment {seg}')

    def _arith(self, op):
        r = self.ram
        sp = r[SP]
        if op == 'neg':
            r[sp - 1] = (-r[sp - 1]) & WORD
        elif op == 'not':
            r[sp - 1] = (~r[sp - 1]) & WORD
        else:
            y = r[sp - 1]
            x = r[sp - 2]
            r[SP] = sp - 1
            if op == 'add':   v = (x + y) & WORD
            elif op == 'sub': v = (x - y) & WORD
            elif op == 'and': v = x & y
            elif op == 'or':  v = x | y
            elif op == 'eq':  v = WORD if _signed(x) == _signed(y) else 0
            elif op == 'gt':  v = WORD if _signed(x) > _signed(y) else 0
            elif op == 'lt':  v = WORD if _signed(x) < _signed(y) else 0
            else: raise ValueError(f'bad op {op}')
            r[sp - 2] = v

    def run(self, max_steps):
        n = 0
        while n < max_steps and self.step():
            n += 1
        return n

    def set_key(self, code):
        self.ram[KBD] = code & WORD

    def peek(self, addr):
        return self.ram[addr]

    def screen_rows(self):
        for r in range(SCREEN_H):
            row = []
            base = SCREEN_BASE + r * 32
            for w in range(32):
                word = self.ram[base + w]
                for bit in range(16):
                    row.append((word >> bit) & 1)
            yield row

def load_dir(path):
    path = Path(path)
    files = sorted(path.glob('*.vm')) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f'no .vm files in {path}')
    return files

def main():
    import argparse
    from tools.emulator import render_ascii
    ap = argparse.ArgumentParser(description='Run .vm bytecode on the VM emulator.')
    ap.add_argument('source', help='.vm file or directory of .vm files')
    ap.add_argument('-s', '--steps', type=int, default=20_000_000,
                    help='max VM steps to execute')
    ap.add_argument('--screen', action='store_true', help='render screen as ASCII')
    args = ap.parse_args()
    emu = VMEmulator(load_dir(args.source))
    ran = emu.run(args.steps)
    print(f'ran {ran} VM steps (halted={emu.halted})')
    if args.screen:
        print(render_ascii(emu))

if __name__ == '__main__':
    main()
