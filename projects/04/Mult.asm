    @R2
    M=0

    @R1
    D=M
    @END
    D;JEQ

(LOOP)
    @R0
    D=M
    @R2
    M=D+M

    @R1
    MD=M-1
    @LOOP
    D;JGT

(END)
    @END
    0;JMP
