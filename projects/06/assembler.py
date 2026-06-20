#!/usr/bin/env python3
"""Hack assembler: translates .asm → .hack (16-bit binary, one instruction per line)."""

import re
import sys
from pathlib import Path

PREDEFINED = {
    'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
    'SCREEN': 16384, 'KBD': 24576,
    **{f'R{i}': i for i in range(16)},
}

COMP = {
    '0':   ('0', '101010'), '1':   ('0', '111111'), '-1':  ('0', '111010'),
    'D':   ('0', '001100'), 'A':   ('0', '110000'), '!D':  ('0', '001101'),
    '!A':  ('0', '110001'), '-D':  ('0', '001111'), '-A':  ('0', '110011'),
    'D+1': ('0', '011111'), 'A+1': ('0', '110111'), 'D-1': ('0', '001110'),
    'A-1': ('0', '110010'), 'D+A': ('0', '000010'), 'D-A': ('0', '010011'),
    'A-D': ('0', '000111'), 'D&A': ('0', '000000'), 'D|A': ('0', '010101'),
    'M':   ('1', '110000'), '!M':  ('1', '110001'), '-M':  ('1', '110011'),
    'M+1': ('1', '110111'), 'M-1': ('1', '110010'), 'D+M': ('1', '000010'),
    'D-M': ('1', '010011'), 'M-D': ('1', '000111'), 'D&M': ('1', '000000'),
    'D|M': ('1', '010101'),
}

DEST = {
    None: '000', 'M': '001', 'D':  '010', 'MD':  '011',
    'A':  '100', 'AM': '101', 'AD': '110', 'AMD': '111',
}

JUMP = {
    None:  '000', 'JGT': '001', 'JEQ': '010', 'JGE': '011',
    'JLT': '100', 'JNE': '101', 'JLE': '110', 'JMP': '111',
}

def clean(line: str) -> str:
    return re.sub(r'//.*', '', line).strip()

def assemble(src: Path) -> str:
    lines = [clean(l) for l in src.read_text().splitlines()]
    lines = [l for l in lines if l]

    symbols = dict(PREDEFINED)
    ic = 0
    for line in lines:
        if line.startswith('(') and line.endswith(')'):
            symbols[line[1:-1]] = ic
        else:
            ic += 1

    next_var = 16
    output: list[str] = []

    for line in lines:
        if line.startswith('('):
            continue

        if line.startswith('@'):
            token = line[1:]
            if token.lstrip('-').isdigit():
                addr = int(token)
            else:
                if token not in symbols:
                    symbols[token] = next_var
                    next_var += 1
                addr = symbols[token]
            output.append(f'{addr:016b}')

        else:
            dest = comp = jump = None
            rest = line
            if '=' in rest:
                dest, rest = rest.split('=', 1)
            if ';' in rest:
                comp, jump = rest.split(';', 1)
            else:
                comp = rest
            a, cccccc = COMP[comp]
            output.append(f'111{a}{cccccc}{DEST[dest]}{JUMP[jump]}')

    return '\n'.join(output) + '\n'

def main():
    if len(sys.argv) < 2:
        print(f'usage: {sys.argv[0]} <file.asm> [...]')
        sys.exit(1)

    for arg in sys.argv[1:]:
        src = Path(arg)
        if not src.exists():
            print(f'error: {src} not found', file=sys.stderr)
            sys.exit(1)
        dest = src.with_suffix('.hack')
        dest.write_text(assemble(src))
        print(f'{src} → {dest}')

if __name__ == '__main__':
    main()
