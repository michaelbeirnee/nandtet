// Mult.asm — R2 = R0 * R1
// Inputs R0, R1 are non-negative; result fits in 15 bits.
// Strategy: repeated addition — add R0 to R2 exactly R1 times.

    @R2
    M=0             // R2 = 0

    @R1
    D=M
    @END
    D;JEQ           // if R1 == 0, done (R2 already 0)

(LOOP)
    @R0
    D=M
    @R2
    M=D+M           // R2 += R0

    @R1
    MD=M-1          // R1--; D = new R1
    @LOOP
    D;JGT           // if R1 > 0, keep going

(END)
    @END
    0;JMP
