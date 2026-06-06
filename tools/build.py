#!/usr/bin/env python3
"""End-to-end Hack build pipeline: Jack source  →  .vm  →  .asm  →  .hack.

Chains the three toolchain stages that live in the numbered project folders:
    projects/10/compiler.py   Jack  → VM
    projects/07/vm.py         VM    → assembly
    projects/06/assembler.py  asm   → Hack binary

A Jack program needs the OS library (project 12) linked in, so by default the
game sources plus the OS are staged into one build directory and compiled
together.

    python3 tools/build.py                       # build Tetris (projects 09 + 12)
    python3 tools/build.py path/to/Game/ -o out  # build any Jack program
"""

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OS_DIR = ROOT / 'projects' / '12'


def _load(name: str, relpath: str):
    """Import a module by file path (project folders aren't valid package names)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


compiler  = _load('compiler',  'projects/10/compiler.py')
vmtrans   = _load('vmtrans',   'projects/07/vm.py')
assembler = _load('assembler', 'projects/06/assembler.py')


def build(src_dir: Path, out_dir: Path, name: str, link_os: bool = True) -> Path:
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    stage = out_dir / 'build'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    # 1. gather Jack sources (game + OS) into one directory
    jacks = sorted(src_dir.glob('*.jack'))
    if not jacks:
        sys.exit(f'no .jack files in {src_dir}')
    sources = list(jacks)
    if link_os:
        os_names = {p.name for p in jacks}
        sources += [p for p in sorted(OS_DIR.glob('*.jack')) if p.name not in os_names]
    for p in sources:
        shutil.copy(p, stage / p.name)
    print(f'[1/3] compiling {len(sources)} Jack files → VM')
    for jack in sorted(stage.glob('*.jack')):
        compiler.compile_file(jack)

    # 2. translate the whole directory to one .asm (with Sys.init bootstrap)
    print('[2/3] translating VM → assembly')
    asm = vmtrans.translate(stage)
    asm_out = out_dir / f'{name}.asm'
    shutil.move(str(asm), asm_out)

    # 3. assemble to a Hack binary
    print('[3/3] assembling → Hack binary')
    hack_out = out_dir / f'{name}.hack'
    hack_out.write_text(assembler.assemble(asm_out))

    n = len(hack_out.read_text().split())
    print(f'✓ {hack_out}  ({n} instructions)')
    if n > 0x8000:
        print(f'  note: {n} > 32768 — exceeds the real Hack 32K ROM; runs under '
              f'the emulator (non-strict ROM) only.')
    return hack_out


def main():
    ap = argparse.ArgumentParser(description='Build a Jack program to a .hack image.')
    ap.add_argument('source', nargs='?', default=str(ROOT / 'projects' / '09'),
                    help='directory of .jack sources (default: projects/09, Tetris)')
    ap.add_argument('-o', '--out', default=str(ROOT / 'dist'),
                    help='output directory (default: dist/)')
    ap.add_argument('-n', '--name', help='output base name (default: source dir name)')
    ap.add_argument('--no-os', action='store_true',
                    help="don't link the project-12 OS library")
    args = ap.parse_args()

    src = Path(args.source)
    name = args.name or ('Tetris' if src.name == '09' else src.name)
    out = build(src, Path(args.out), name, link_os=not args.no_os)
    print(f'\nRun it:  python3 tools/emulator.py {out} --screen')


if __name__ == '__main__':
    main()
