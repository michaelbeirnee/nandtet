#!/usr/bin/env python3
"""Jack compiler (Projects 10+11): .jack → .vm
   Single-pass: tokenize → parse → emit VM code directly.
   Accepts a single .jack file or a directory of .jack files.
"""

import re
import sys
from pathlib import Path

# ── tokenizer ─────────────────────────────────────────────────────────────────

KEYWORDS = {
    'class', 'constructor', 'function', 'method', 'field', 'static',
    'var', 'int', 'char', 'boolean', 'void', 'true', 'false', 'null',
    'this', 'let', 'do', 'if', 'else', 'while', 'return',
}

_TOKEN_RE = re.compile(
    r'"[^"]*"'                     # string constant  (must come first)
    r'|//[^\n]*'                   # line comment
    r'|/\*.*?\*/'                  # block comment
    r'|[{}()\[\].,;+\-*/&|<>=~]'  # single-char symbols
    r'|\d+'                        # integer constant
    r'|[A-Za-z_]\w*',             # identifier / keyword
    re.DOTALL,
)


class Tokenizer:
    def __init__(self, src: str):
        raw = _TOKEN_RE.findall(src)
        self._toks = [t for t in raw
                      if not t.startswith('//') and not t.startswith('/*')]
        self._pos = 0

    def has_more(self) -> bool:
        return self._pos < len(self._toks)

    def peek(self) -> str:
        return self._toks[self._pos]

    def advance(self) -> str:
        t = self._toks[self._pos]; self._pos += 1; return t

    def expect(self, val: str) -> str:
        t = self.advance()
        if t != val:
            raise SyntaxError(f'expected {val!r}, got {t!r} (pos {self._pos})')
        return t

    def peek_is(self, *vals) -> bool:
        return self.has_more() and self.peek() in vals


# ── symbol table ──────────────────────────────────────────────────────────────

_VM_SEG = {
    'static': 'static', 'field': 'this',
    'argument': 'argument', 'var': 'local',
}


class SymbolTable:
    def __init__(self):
        self._class: dict[str, tuple] = {}
        self._sub:   dict[str, tuple] = {}
        self._count = {k: 0 for k in ('static', 'field', 'argument', 'var')}

    def start_subroutine(self):
        self._sub = {}
        self._count['argument'] = 0
        self._count['var'] = 0

    def define(self, name: str, typ: str, kind: str):
        tbl = self._class if kind in ('static', 'field') else self._sub
        tbl[name] = (typ, kind, self._count[kind])
        self._count[kind] += 1

    def count(self, kind: str) -> int:
        return self._count[kind]

    def _get(self, name: str):
        return self._sub.get(name) or self._class.get(name)

    def contains(self, name: str) -> bool:  return self._get(name) is not None
    def type_of(self,  name: str) -> str:   return self._get(name)[0]
    def kind_of(self,  name: str) -> str:   return self._get(name)[1]
    def index_of(self, name: str) -> int:   return self._get(name)[2]
    def segment(self,  name: str) -> str:   return _VM_SEG[self.kind_of(name)]


# ── compilation engine ────────────────────────────────────────────────────────

_BINARY_OP = {
    '+': 'add', '-': 'sub', '&': 'and', '|': 'or',
    '<': 'lt',  '>': 'gt',  '=': 'eq',
}


class Compiler:
    def __init__(self, src: str, out: list):
        self._tok  = Tokenizer(src)
        self._sym  = SymbolTable()
        self._out  = out
        self._uid  = 0
        self._cls  = ''

    def _n(self) -> int:
        v = self._uid; self._uid += 1; return v

    def _emit(self, *lines):
        self._out.extend(lines)

    # ── class ─────────────────────────────────────────────────────────────────

    def compile_class(self):
        t = self._tok
        t.expect('class')
        self._cls = t.advance()
        t.expect('{')
        while t.peek_is('static', 'field'):
            self._class_var_dec()
        while t.peek_is('constructor', 'function', 'method'):
            self._subroutine()
        t.expect('}')

    def _class_var_dec(self):
        t = self._tok
        kind = t.advance()       # static | field
        typ  = t.advance()
        self._sym.define(t.advance(), typ, kind)
        while t.peek_is(','):
            t.advance(); self._sym.define(t.advance(), typ, kind)
        t.expect(';')

    # ── subroutine ────────────────────────────────────────────────────────────

    def _subroutine(self):
        t = self._tok
        kind = t.advance()       # constructor | function | method
        t.advance()              # return type
        name = t.advance()
        self._sym.start_subroutine()

        if kind == 'method':
            # arg 0 is always 'this' for methods
            self._sym.define('this', self._cls, 'argument')

        t.expect('('); self._param_list(); t.expect(')')
        t.expect('{')
        while t.peek_is('var'):
            self._var_dec()

        self._emit(f'function {self._cls}.{name} {self._sym.count("var")}')

        if kind == 'constructor':
            self._emit(f'push constant {self._sym.count("field")}',
                       'call Memory.alloc 1', 'pop pointer 0')
        elif kind == 'method':
            self._emit('push argument 0', 'pop pointer 0')

        self._statements()
        t.expect('}')

    def _param_list(self):
        t = self._tok
        if t.peek_is(')'):
            return
        typ = t.advance(); self._sym.define(t.advance(), typ, 'argument')
        while t.peek_is(','):
            t.advance(); typ = t.advance(); self._sym.define(t.advance(), typ, 'argument')

    def _var_dec(self):
        t = self._tok
        t.expect('var'); typ = t.advance()
        self._sym.define(t.advance(), typ, 'var')
        while t.peek_is(','):
            t.advance(); self._sym.define(t.advance(), typ, 'var')
        t.expect(';')

    # ── statements ────────────────────────────────────────────────────────────

    def _statements(self):
        dispatch = {
            'let': self._let, 'if': self._if, 'while': self._while,
            'do': self._do, 'return': self._return,
        }
        while self._tok.has_more() and self._tok.peek() in dispatch:
            dispatch[self._tok.peek()]()

    def _let(self):
        t = self._tok
        t.expect('let')
        name   = t.advance()
        is_arr = t.peek_is('[')

        if is_arr:
            t.advance()
            self._emit(f'push {self._sym.segment(name)} {self._sym.index_of(name)}')
            self._expression()
            self._emit('add')
            t.expect(']')

        t.expect('='); self._expression(); t.expect(';')

        if is_arr:
            # stack: [... target_addr, value]
            self._emit('pop temp 0', 'pop pointer 1', 'push temp 0', 'pop that 0')
        else:
            self._emit(f'pop {self._sym.segment(name)} {self._sym.index_of(name)}')

    def _if(self):
        t = self._tok
        n = self._n()
        else_lbl, end_lbl = f'IF_ELSE_{n}', f'IF_END_{n}'

        t.expect('if'); t.expect('(')
        self._expression()
        t.expect(')')
        self._emit('not', f'if-goto {else_lbl}')
        t.expect('{'); self._statements(); t.expect('}')
        self._emit(f'goto {end_lbl}', f'label {else_lbl}')

        if t.peek_is('else'):
            t.advance(); t.expect('{'); self._statements(); t.expect('}')

        self._emit(f'label {end_lbl}')

    def _while(self):
        t = self._tok
        n = self._n()
        top, end = f'WHILE_TOP_{n}', f'WHILE_END_{n}'

        t.expect('while'); t.expect('(')
        self._emit(f'label {top}')
        self._expression()
        t.expect(')')
        self._emit('not', f'if-goto {end}')
        t.expect('{'); self._statements(); t.expect('}')
        self._emit(f'goto {top}', f'label {end}')

    def _do(self):
        self._tok.expect('do')
        self._subroutine_call()
        self._tok.expect(';')
        self._emit('pop temp 0')   # void return value discarded

    def _return(self):
        t = self._tok
        t.expect('return')
        if t.peek_is(';'):
            self._emit('push constant 0')  # void
        else:
            self._expression()
        t.expect(';')
        self._emit('return')

    # ── expressions ───────────────────────────────────────────────────────────

    def _expression(self):
        self._term()
        while self._tok.has_more() and self._tok.peek() in _BINARY_OP or \
              (self._tok.has_more() and self._tok.peek() in ('*', '/')):
            op = self._tok.advance()
            self._term()
            if   op == '*': self._emit('call Math.multiply 2')
            elif op == '/': self._emit('call Math.divide 2')
            else:           self._emit(_BINARY_OP[op])

    def _term(self):
        t = self._tok
        tok = t.peek()

        if tok.lstrip('-').isdigit() and not tok.startswith('-'):
            t.advance(); self._emit(f'push constant {tok}')

        elif tok.startswith('"'):
            t.advance()
            s = tok[1:-1]
            self._emit(f'push constant {len(s)}', 'call String.new 1')
            for ch in s:
                self._emit(f'push constant {ord(ch)}', 'call String.appendChar 2')

        elif tok == 'true':
            t.advance(); self._emit('push constant 0', 'not')
        elif tok in ('false', 'null'):
            t.advance(); self._emit('push constant 0')
        elif tok == 'this':
            t.advance(); self._emit('push pointer 0')

        elif tok == '(':
            t.advance(); self._expression(); t.expect(')')

        elif tok in ('-', '~'):
            t.advance(); self._term()
            self._emit('neg' if tok == '-' else 'not')

        else:
            name = t.advance()
            if t.peek_is('['):
                # array read: push base + index, pop pointer 1, push that 0
                t.advance()
                self._emit(f'push {self._sym.segment(name)} {self._sym.index_of(name)}')
                self._expression(); t.expect(']')
                self._emit('add', 'pop pointer 1', 'push that 0')
            elif t.peek_is('(', '.'):
                self._subroutine_call(name)
            else:
                self._emit(f'push {self._sym.segment(name)} {self._sym.index_of(name)}')

    def _subroutine_call(self, first: str = None):
        t = self._tok
        if first is None:
            first = t.advance()
        n_args = 0

        if t.peek_is('.'):
            t.advance()
            method = t.advance()
            if self._sym.contains(first):
                # instance.method(...)  — push object as arg 0
                self._emit(f'push {self._sym.segment(first)} {self._sym.index_of(first)}')
                n_args  = 1
                callee  = f'{self._sym.type_of(first)}.{method}'
            else:
                # ClassName.function(...)
                callee = f'{first}.{method}'
        else:
            # bare name(...)  — implicit this
            self._emit('push pointer 0')
            n_args = 1
            callee = f'{self._cls}.{first}'

        t.expect('(')
        n_args += self._expression_list()
        t.expect(')')
        self._emit(f'call {callee} {n_args}')

    def _expression_list(self) -> int:
        n = 0
        if not self._tok.peek_is(')'):
            self._expression(); n = 1
            while self._tok.peek_is(','):
                self._tok.advance(); self._expression(); n += 1
        return n


# ── driver ────────────────────────────────────────────────────────────────────

def compile_file(path: Path) -> Path:
    lines: list[str] = []
    Compiler(path.read_text(), lines).compile_class()
    out = path.with_suffix('.vm')
    out.write_text('\n'.join(lines) + '\n')
    return out


def main():
    if len(sys.argv) != 2:
        print(f'usage: {sys.argv[0]} <File.jack | directory/>')
        sys.exit(1)
    target = Path(sys.argv[1])
    files = sorted(target.glob('*.jack')) if target.is_dir() else [target]
    for f in files:
        out = compile_file(f)
        print(f'{f} → {out}')


if __name__ == '__main__':
    main()
