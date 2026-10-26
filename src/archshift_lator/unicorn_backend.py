"""Optional broad AArch64 CPU backend using Unicorn.

This executes raw ARM64 machine-code snippets on non-ARM hosts. It is not a
Mach-O process runtime: dyld, macOS framework calls, process semantics, and
JIT translation are separate layers and remain incomplete.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

try:
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X16, UC_ARM64_REG_X30
except ImportError as exc:  # keep core CLI usable without optional runtime deps
    Uc = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass
class ExecutionResult:
    instruction_count: int
    exit_code: int
    stopped_reason: str
    trace: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


class RuntimeUnavailable(RuntimeError):
    pass


class GuestExecutionError(RuntimeError):
    pass


def emulate_raw_arm64(
    code: bytes,
    *,
    base: int = 0x100000000,
    max_instructions: int = 1_000_000,
    trace_limit: int = 250,
) -> ExecutionResult:
    """Interpret a raw AArch64 code blob with a tiny Darwin syscall shim.

    Supported shim syscalls: Darwin BSD exit (1), write (4). Unknown syscalls
    fail closed instead of pretending the operation succeeded.
    """
    if Uc is None:
        raise RuntimeUnavailable(
            "Install the optional runtime dependencies with "
            "'python -m pip install -e .[runtime]' to enable Unicorn execution."
        ) from _IMPORT_ERROR
    if not code:
        raise ValueError("ARM64 code blob is empty")
    if len(code) % 4:
        raise ValueError("ARM64 code length must be a multiple of 4 bytes")
    if base % 0x1000:
        raise ValueError("Code base must be 4 KiB aligned")

    page = 0x1000
    code_size = ((len(code) + page - 1) // page) * page
    stack_base = 0x700000000000
    stack_size = 2 * 1024 * 1024
    sentinel = base + code_size

    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(base, code_size)
    uc.mem_write(base, code)
    uc.mem_map(stack_base, stack_size)
    uc.reg_write(UC_ARM64_REG_SP, stack_base + stack_size - 16)
    uc.reg_write(UC_ARM64_REG_X30, sentinel)

    trace: list[str] = []
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    count = 0
    stopped_reason = "returned"
    exit_code = 0

    def on_code(machine, address, size, _user_data):
        nonlocal count, stopped_reason, exit_code
        count += 1
        if count > max_instructions:
            stopped_reason = f"instruction limit exceeded ({max_instructions})"
            machine.emu_stop()
            return
        if len(trace) < trace_limit:
            raw = bytes(machine.mem_read(address, min(size, 4)))
            word = int.from_bytes(raw.ljust(4, b"\0"), "little")
            trace.append(f"0x{address:016x}: 0x{word:08x}")
        # SVC #0x80 is Darwin's conventional ARM64 syscall trap.
        raw = bytes(machine.mem_read(address, 4))
        word = int.from_bytes(raw, "little")
        if (word & 0xFFE0001F) != 0xD4000001 or ((word >> 5) & 0xFFFF) != 0x80:
            return
        syscall = machine.reg_read(UC_ARM64_REG_X16)
        a0 = machine.reg_read(UC_ARM64_REG_X0)
        a1 = machine.reg_read(UC_ARM64_REG_X1)
        a2 = machine.reg_read(UC_ARM64_REG_X2)
        if syscall == 1:  # exit
            exit_code = a0 & 0xFF
            stopped_reason = "guest called exit"
            machine.emu_stop()
        elif syscall == 4:  # write
            if a2 > 16 * 1024 * 1024:
                stopped_reason = "write request exceeds safety limit"
                machine.emu_stop()
                return
            try:
                data = bytes(machine.mem_read(a1, a2))
            except Exception:
                stopped_reason = "guest write used an invalid memory address"
                machine.emu_stop()
                return
            if a0 == 1:
                stdout_chunks.append(data)
            elif a0 == 2:
                stderr_chunks.append(data)
            machine.reg_write(UC_ARM64_REG_X0, len(data))
        else:
            stopped_reason = f"unsupported Darwin syscall {syscall}"
            machine.emu_stop()

    uc.hook_add(UC_HOOK_CODE, on_code)
    try:
        uc.emu_start(base, sentinel, count=max_instructions + 1)
    except Exception as exc:
        if stopped_reason == "returned":
            raise GuestExecutionError(f"Guest stopped at an emulation fault: {exc}") from exc
    return ExecutionResult(
        instruction_count=count,
        exit_code=exit_code,
        stopped_reason=stopped_reason,
        trace=trace,
        stdout=b"".join(stdout_chunks).decode("utf-8", errors="replace"),
        stderr=b"".join(stderr_chunks).decode("utf-8", errors="replace"),
    )


def emulate_raw_file(path: str | Path, **kwargs) -> ExecutionResult:
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    return emulate_raw_arm64(p.read_bytes(), **kwargs)
