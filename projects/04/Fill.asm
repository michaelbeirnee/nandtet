(MAINLOOP)
    @KBD
    D=M
    @SETWHITE
    D;JEQ

(SETBLACK)
    @color
    M=-1
    @DRAW
    0;JMP

(SETWHITE)
    @color
    M=0

(DRAW)
    @SCREEN
    D=A
    @addr
    M=D

    @8192
    D=A
    @n
    M=D

(FILLLOOP)
    @n
    D=M
    @MAINLOOP
    D;JLE

    @color
    D=M
    @addr
    A=M
    M=D

    @addr
    M=M+1

    @n
    M=M-1

    @FILLLOOP
    0;JMP
