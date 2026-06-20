#!/usr/bin/env python3
"""Hack VM Translator: .vm bytecode → Hack assembly (.asm).
   Covers Projects 07 (arithmetic + memory segments) and 08 (flow + functions).
   Accepts a single .vm file or a directory; writes one .asm file.
"""

import re
import sys
from pathlib import Path

SEG_BASE = {'local': 'LCL', 'argument': 'ARG', 'this': 'THIS', 'that': 'THAT'}
TEMP_BASE = 5
PTR_BASE  = 3

class CodeGen:
    def __init__(self):
        self._uid = 0
        self.function = ''

    def _n(self) -> int:
        n = self._uid; self._uid += 1; return n

    @staticmethod
    def _push_d() -> list:
        return ['@SP', 'A=M', 'M=D', '@SP', 'M=M+1']

    @staticmethod
    def _pop_d() -> list:
        return ['@SP', 'AM=M-1', 'D=M']

    def arith(self, cmd: str) -> list:
        simple = {
            'add': ['@SP', 'AM=M-1', 'D=M', 'A=A-1', 'M=D+M'],
            'sub': ['@SP', 'AM=M-1', 'D=M', 'A=A-1', 'M=M-D'],
            'and': ['@SP', 'AM=M-1', 'D=M', 'A=A-1', 'M=D&M'],
            'or':  ['@SP', 'AM=M-1', 'D=M', 'A=A-1', 'M=D|M'],
            'neg': ['@SP', 'A=M-1', 'M=-M'],
            'not': ['@SP', 'A=M-1', 'M=!M'],
        }
        if cmd in simple:
            return simple[cmd]
        jmp = {'eq': 'JEQ', 'lt': 'JLT', 'gt': 'JGT'}[cmd]
        return self._cmp(jmp)

    def _cmp(self, jmp: str) -> list:
        n = self._n()
        t, e = f'CMP_T_{n}', f'CMP_E_{n}'
        return [
            '@SP', 'AM=M-1', 'D=M',
            'A=A-1', 'D=M-D',
            f'@{t}', f'D;{jmp}',
            '@SP', 'A=M-1', 'M=0',
            f'@{e}', '0;JMP',
            f'({t})', '@SP', 'A=M-1', 'M=-1',
            f'({e})',
        ]

    def push(self, seg: str, i: int, fname: str) -> list:
        if seg == 'constant':
            return [f'@{i}', 'D=A'] + self._push_d()
        if seg in SEG_BASE:
            base = SEG_BASE[seg]
            return [f'@{i}', 'D=A', f'@{base}', 'A=D+M', 'D=M'] + self._push_d()
        if seg == 'temp':
            return [f'@{TEMP_BASE + i}', 'D=M'] + self._push_d()
        if seg == 'pointer':
            return [f'@{PTR_BASE + i}', 'D=M'] + self._push_d()
        if seg == 'static':
            return [f'@{fname}.{i}', 'D=M'] + self._push_d()
        raise ValueError(f'unknown segment: {seg}')

    def pop(self, seg: str, i: int, fname: str) -> list:
        if seg in SEG_BASE:
            base = SEG_BASE[seg]
            return [
                f'@{i}', 'D=A', f'@{base}', 'D=D+M', '@R13', 'M=D',
                '@SP', 'AM=M-1', 'D=M', '@R13', 'A=M', 'M=D',
            ]
        if seg == 'temp':    return self._pop_d() + [f'@{TEMP_BASE + i}', 'M=D']
        if seg == 'pointer': return self._pop_d() + [f'@{PTR_BASE + i}', 'M=D']
        if seg == 'static':  return self._pop_d() + [f'@{fname}.{i}', 'M=D']
        raise ValueError(f'unknown segment: {seg}')

    def label(self, lbl: str) -> list:
        return [f'({self.function}${lbl})']

    def goto(self, lbl: str) -> list:
        return [f'@{self.function}${lbl}', '0;JMP']

    def if_goto(self, lbl: str) -> list:
        return self._pop_d() + [f'@{self.function}${lbl}', 'D;JNE']

    def function_decl(self, name: str, n_vars: int) -> list:
        self.function = name
        init = []
        for _ in range(n_vars):
            init += ['@SP', 'A=M', 'M=0', '@SP', 'M=M+1']
        return [f'({name})'] + init

    def call(self, name: str, n_args: int) -> list:
        n = self._n()
        ret = f'{name}$ret.{n}'
        return [
            f'@{ret}',  'D=A',  '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            '@LCL',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            '@ARG',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            '@THIS', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            '@THAT', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            '@SP', 'D=M', f'@{n_args + 5}', 'D=D-A', '@ARG', 'M=D',
            '@SP', 'D=M', '@LCL', 'M=D',
            f'@{name}', '0;JMP',
            f'({ret})',
        ]

    def return_cmd(self) -> list:
        return [
            '@LCL', 'D=M', '@R14', 'M=D',
            '@5', 'A=D-A', 'D=M', '@R15', 'M=D',
            '@SP', 'AM=M-1', 'D=M',
            '@ARG', 'A=M', 'M=D',
            '@ARG', 'D=M+1', '@SP', 'M=D',
            '@R14', 'AM=M-1', 'D=M', '@THAT', 'M=D',
            '@R14', 'AM=M-1', 'D=M', '@THIS', 'M=D',
            '@R14', 'AM=M-1', 'D=M', '@ARG',  'M=D',
            '@R14', 'AM=M-1', 'D=M', '@LCL',  'M=D',
            '@R15', 'A=M', '0;JMP',
        ]

def translate_file(path: Path, gen: CodeGen) -> list:
    out = [f'// === {path.name} ===']
    fname = path.stem
    for raw in path.read_text().splitlines():
        line = re.sub(r'//.*', '', raw).strip()
        if not line:
            continue
        out.append(f'// {line}')
        parts = line.split()
        cmd   = parts[0]

        if cmd in ('add', 'sub', 'neg', 'eq', 'lt', 'gt', 'and', 'or', 'not'):
            out += gen.arith(cmd)
        elif cmd == 'push':
            out += gen.push(parts[1], int(parts[2]), fname)
        elif cmd == 'pop':
            out += gen.pop(parts[1], int(parts[2]), fname)
        elif cmd == 'label':
            out += gen.label(parts[1])
        elif cmd == 'goto':
            out += gen.goto(parts[1])
        elif cmd == 'if-goto':
            out += gen.if_goto(parts[1])
        elif cmd == 'function':
            out += gen.function_decl(parts[1], int(parts[2]))
        elif cmd == 'call':
            out += gen.call(parts[1], int(parts[2]))
        elif cmd == 'return':
            out += gen.return_cmd()
        else:
            raise ValueError(f'unknown VM command: {cmd!r}')

    return out

def translate(target: Path) -> Path:
    gen = CodeGen()
    lines: list = []

    if target.is_dir():
        vm_files = sorted(target.glob('*.vm'))
        if not vm_files:
            raise FileNotFoundError(f'no .vm files in {target}')
        lines += ['// bootstrap', '@256', 'D=A', '@SP', 'M=D']
        lines += gen.call('Sys.init', 0)
        for f in vm_files:
            lines += translate_file(f, gen)
        out_path = target / (target.name + '.asm')
    else:
        lines += translate_file(target, gen)
        out_path = target.with_suffix('.asm')

    out_path.write_text('\n'.join(lines) + '\n')
    return out_path

def main():
    if len(sys.argv) != 2:
        print(f'usage: {sys.argv[0]} <file.vm | directory/>')
        sys.exit(1)
    target = Path(sys.argv[1])
    if not target.exists():
        print(f'error: {target} not found', file=sys.stderr)
        sys.exit(1)
    out = translate(target)
    print(f'→ {out}')

if __name__ == '__main__':
    main()
