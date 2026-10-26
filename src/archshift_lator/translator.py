"""Experimental AArch64 basic-block translator to x86-64 assembly.

The translator supports straight-line blocks containing NOP, MOVZ, ADD/SUB
immediate and RET X30. It emits a callable x86-64 function using an explicit
spill slot for each guest register. Branches, loads/stores, SIMD, calls, and OS
interactions are intentionally rejected until their semantics are implemented.
"""
from __future__ import annotations
from pathlib import Path

from .arm64 import UnsupportedInstruction


GUEST_REGS = 31
FRAME_SIZE = 256  # 31 * 8 bytes plus alignment padding


def _slot(index: int) -> int:
    if not 0 <= index < GUEST_REGS:
        raise UnsupportedInstruction(f"Register X{index} is not supported in this instruction")
    return 8 * (index + 1)


def _mem(index: int, width: int = 64) -> str:
    size = "qword" if width == 64 else "dword"
    return f"{size} ptr [rbp - {_slot(index)}]"


def translate_words(words: list[int], function_name: str = "archshift_guest") -> str:
    """Translate a linear AArch64 code sequence into Intel-syntax x86-64 asm."""
    if not words:
        raise ValueError("No ARM64 instructions were supplied")
    if not function_name.isidentifier():
        raise ValueError("Function name must be a plain identifier")
    normalized = [word & 0xFFFFFFFF for word in words]
    lines = [
        ".intel_syntax noprefix",
        ".text",
        f".global {function_name}",
        f"{function_name}:",
        "    push rbp",
        "    mov rbp, rsp",
        f"    sub rsp, {FRAME_SIZE}",
    ]
    # Darwin/Unix x86-64 ABI arguments become guest X0-X7 at entry.
    for reg, host in enumerate(("rdi", "rsi", "rdx", "rcx", "r8", "r9")):
        lines.append(f"    mov {_mem(reg)}, {host}")
    lines.extend([
        f"    mov rax, qword ptr [rbp + 16]",
        f"    mov {_mem(6)}, rax",
        f"    mov rax, qword ptr [rbp + 24]",
        f"    mov {_mem(7)}, rax",
    ])
    for reg in range(8, GUEST_REGS):
        lines.append(f"    mov qword ptr [rbp - {_slot(reg)}], 0")

    saw_ret = False
    for index, word in enumerate(normalized):
        if saw_ret:
            raise UnsupportedInstruction("Instructions after RET are unreachable")
        if word == 0xD503201F:  # NOP
            lines.append("    nop")
            continue

        # MOVZ Xd/Wd, #imm16, LSL #0/#16/#32/#48
        if (word & 0x7F800000) == 0x52800000:
            is64 = bool(word & 0x80000000)
            width = 64 if is64 else 32
            rd = word & 31
            imm16 = (word >> 5) & 0xFFFF
            half = (word >> 21) & 3
            if rd == 31:
                raise UnsupportedInstruction("MOVZ to XZR/WZR is not supported by this translator")
            if not is64 and half > 1:
                raise UnsupportedInstruction("MOVZ Wd shift cannot exceed 16")
            value = imm16 << (half * 16)
            if width == 64:
                lines.append(f"    mov rax, 0x{value:x}")
            else:
                lines.append(f"    mov eax, 0x{value:x}")
            lines.append(f"    mov {_mem(rd)}, rax")
            continue

        # ADD/SUB (immediate), without flag updates. SP/ZR operands excluded.
        if (word & 0x1F000000) == 0x11000000:
            is64 = bool(word & 0x80000000)
            width = 64 if is64 else 32
            subtract = bool(word & (1 << 30))
            rd = word & 31
            rn = (word >> 5) & 31
            if rd == 31 or rn == 31:
                raise UnsupportedInstruction("ADD/SUB using SP or ZR is not supported by this translator")
            imm = (word >> 10) & 0xFFF
            if word & (1 << 22):
                imm <<= 12
            if width == 64:
                lines.append(f"    mov rax, {_mem(rn)}")
                lines.append(f"    {'sub' if subtract else 'add'} rax, {imm}")
            else:
                lines.append(f"    mov eax, dword ptr [rbp - {_slot(rn)}]")
                lines.append(f"    {'sub' if subtract else 'add'} eax, {imm}")
            lines.append(f"    mov {_mem(rd)}, rax")
            continue

        # RET X30 (architectural return from this translated function).
        if (word & 0xFFFFFC1F) == 0xD65F0000:
            rn = (word >> 5) & 31
            if rn != 30:
                raise UnsupportedInstruction("Only RET X30 is supported at the end of a block")
            if index != len(normalized) - 1:
                raise UnsupportedInstruction("RET must be the final instruction")
            lines.extend([
                f"    mov rax, {_mem(0)}",
                "    mov rsp, rbp",
                "    pop rbp",
                "    ret",
            ])
            saw_ret = True
            continue

        raise UnsupportedInstruction(f"No x86-64 translation for ARM64 word 0x{word:08x} at index {index}")

    if not saw_ret:
        raise UnsupportedInstruction("Block has no RET X30; control-flow exits are not supported yet")
    lines.append(f".size {function_name}, .-{function_name}")
    return "\n".join(lines) + "\n"


def translate_raw_file(path: str | Path, function_name: str = "archshift_guest") -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    raw = p.read_bytes()
    if not raw or len(raw) % 4:
        raise ValueError("Raw ARM64 code must contain a non-empty multiple of 4 bytes")
    words = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]
    return translate_words(words, function_name=function_name)
