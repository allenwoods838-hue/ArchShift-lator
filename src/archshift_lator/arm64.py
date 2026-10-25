"""Small AArch64 instruction lab; not a complete CPU emulator."""
from __future__ import annotations
from dataclasses import dataclass, field


class UnsupportedInstruction(ValueError):
    pass


@dataclass
class ARM64State:
    x: list[int] = field(default_factory=lambda: [0] * 31)
    sp: int = 0
    pc: int = 0
    halted: bool = False

    def read_reg(self, index: int, width: int = 64) -> int:
        value = self.sp if index == 31 else self.x[index]
        return value & ((1 << width) - 1)

    def write_reg(self, index: int, value: int, width: int = 64) -> None:
        value &= (1 << width) - 1
        if index == 31:
            self.sp = value
        else:
            self.x[index] = value


@dataclass
class StepResult:
    pc: int
    word: int
    mnemonic: str
    detail: str = ""


def decode_and_step(word: int, state: ARM64State) -> StepResult:
    word &= 0xFFFFFFFF
    old_pc = state.pc
    if word == 0xD503201F:
        state.pc += 4
        return StepResult(old_pc, word, "NOP")
    if (word & 0xFFFFFC1F) == 0xD65F0000:
        rn = (word >> 5) & 0x1F
        state.pc = state.read_reg(rn)
        state.halted = True
        return StepResult(old_pc, word, "RET", f"PC <- X{rn}")
    if (word & 0x7F800000) == 0x52800000:
        is64 = bool(word & 0x80000000)
        width = 64 if is64 else 32
        rd = word & 31
        imm16 = (word >> 5) & 0xFFFF
        half = (word >> 21) & 3
        if not is64 and half > 1:
            raise UnsupportedInstruction("MOVZ Wd shift cannot exceed 16")
        value = (imm16 << (half * 16)) & ((1 << width) - 1)
        state.write_reg(rd, value, width)
        state.pc += 4
        return StepResult(old_pc, word, "MOVZ", f"reg {rd} <- 0x{value:x}")
    if (word & 0x1F000000) == 0x11000000:
        is64 = bool(word & 0x80000000)
        width = 64 if is64 else 32
        sub = bool(word & (1 << 30))
        rd = word & 31
        rn = (word >> 5) & 31
        imm = (word >> 10) & 0xFFF
        if word & (1 << 22):
            imm <<= 12
        lhs = state.read_reg(rn, width)
        state.write_reg(rd, lhs - imm if sub else lhs + imm, width)
        state.pc += 4
        return StepResult(old_pc, word, "SUB" if sub else "ADD", f"reg {rd} <- 0x{state.read_reg(rd, width):x}")
    raise UnsupportedInstruction(f"Unsupported AArch64 word 0x{word:08x} at PC 0x{old_pc:x}")


def run_words(words: list[int], max_steps: int = 1000) -> tuple[ARM64State, list[StepResult]]:
    state = ARM64State()
    trace = []
    for word in words[:max_steps]:
        if state.halted:
            break
        trace.append(decode_and_step(word, state))
    if len(words) > max_steps and not state.halted:
        raise RuntimeError(f"Instruction limit ({max_steps}) exceeded")
    return state, trace
