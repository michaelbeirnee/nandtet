// Fill.asm — keyboard-driven screen fill
// Polls the keyboard in an infinite loop.
// Key pressed  → fill entire screen black (all 1s)
// No key       → fill entire screen white (all 0s)
// Screen is 256 rows × 32 words = 8192 words starting at SCREEN (16384).

(MAINLOOP)
    @KBD
    D=M
    @SETWHITE
    D;JEQ           // no key pressed

(SETBLACK)
    @color
    M=-1            // 0xFFFF — all pixels on
    @DRAW
    0;JMP

(SETWHITE)
    @color
    M=0             // all pixels off

(DRAW)
    @SCREEN
    D=A
    @addr
    M=D             // addr = start of screen

    @8192
    D=A
    @n
    M=D             // n = number of words to fill

(FILLLOOP)
    @n
    D=M
    @MAINLOOP
    D;JLE           // filled all words — poll again

    @color
    D=M
    @addr
    A=M
    M=D             // RAM[addr] = color

    @addr
    M=M+1           // advance pointer

    @n
    M=M-1           // one fewer word to fill

    @FILLLOOP
    0;JMP
