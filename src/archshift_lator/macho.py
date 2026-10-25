"""Read-only Mach-O architecture inspection for thin and fat binaries."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import BinaryIO

CPU_NAMES = {7: "i386", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64"}
THIN_MAGICS = {
    b"\xce\xfa\xed\xfe": ("<", False), b"\xcf\xfa\xed\xfe": ("<", True),
    b"\xfe\xed\xfa\xce": (">", False), b"\xfe\xed\xfa\xcf": (">", True),
}
FAT_MAGICS = {
    b"\xca\xfe\xba\xbe": (">", False), b"\xbe\xba\xfe\xca": ("<", False),
    b"\xca\xfe\xba\xbf": (">", True), b"\xbf\xba\xfe\xca": ("<", True),
}
LC_CODE_SIGNATURE = 0x1D
DYLIB_COMMANDS = {0xC, 0xD, 0x80000018, 0x8000001F, 0x20, 0x80000023}


class MachOError(ValueError):
    """File is not a supported Mach-O container."""


@dataclass
class MachOInfo:
    path: str
    file_size: int
    is_fat: bool = False
    architectures: list[str] = field(default_factory=list)
    cpu_types: list[int] = field(default_factory=list)
    file_type: int | None = None
    file_type_name: str = "unknown"
    is_64_bit: bool | None = None
    load_commands: int = 0
    linked_libraries: list[str] = field(default_factory=list)
    has_code_signature: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def has_x86_64(self) -> bool:
        return "x86_64" in self.architectures

    @property
    def has_arm64(self) -> bool:
        return "arm64" in self.architectures


def _name(cpu: int) -> str:
    cpu &= 0xFFFFFFFF
    return CPU_NAMES.get(cpu, f"unknown-cpu-0x{cpu:08x}")


def _kind(value: int) -> str:
    return {1: "object", 2: "executable", 6: "dylib", 8: "bundle", 11: "kext bundle"}.get(value, f"file-type-{value}")


def _cstring(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", errors="replace")


def inspect_macho(path: str | Path) -> MachOInfo:
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Not a regular file: {p}")
    info = MachOInfo(str(p), p.stat().st_size)
    with p.open("rb") as stream:
        head = stream.read(4096)
        if len(head) < 4:
            raise MachOError("File is too small to contain a Mach-O header")
        if head[:4] in FAT_MAGICS:
            endian, fat64 = FAT_MAGICS[head[:4]]
            info.is_fat = True
            if len(head) < 8:
                raise MachOError("Truncated fat Mach-O header")
            count = struct.unpack_from(endian + "I", head, 4)[0]
            if count > 64:
                raise MachOError("Implausible architecture count")
            fmt = endian + ("iiQQII" if fat64 else "iiIII")
            rec_size = struct.calcsize(fmt)
            table_size = 8 + count * rec_size
            if table_size > len(head):
                stream.seek(0)
                head = stream.read(table_size)
            entries = []
            for i in range(count):
                pos = 8 + i * rec_size
                if pos + rec_size > len(head):
                    raise MachOError("Truncated fat architecture table")
                ent = struct.unpack_from(fmt, head, pos)
                entries.append(ent)
                cpu = ent[0] & 0xFFFFFFFF
                info.cpu_types.append(cpu)
                arch = _name(cpu)
                if arch not in info.architectures:
                    info.architectures.append(arch)
            for ent in entries:
                stream.seek(ent[2])
                slice_head = stream.read(4096)
                if slice_head[:4] in THIN_MAGICS:
                    _parse_thin(stream, slice_head, info, ent[2])
                    break
            if count == 0:
                raise MachOError("Fat Mach-O architecture table is empty")
            return info
        if head[:4] not in THIN_MAGICS:
            raise MachOError("File does not have a recognized Mach-O magic number")
        _parse_thin(stream, head, info)
    return info


def _parse_thin(stream: BinaryIO, head: bytes, info: MachOInfo, base_offset: int = 0) -> None:
    endian, is64 = THIN_MAGICS[head[:4]]
    header_size = 32 if is64 else 28
    if len(head) < header_size:
        raise MachOError("Truncated Mach-O header")
    cpu, _subcpu, kind, ncmds, sizeofcmds = struct.unpack_from(endian + "iiIII", head, 4)
    if not info.is_fat:
        val = cpu & 0xFFFFFFFF
        info.cpu_types = [val]
        info.architectures = [_name(val)]
    info.is_64_bit = is64
    info.file_type = kind
    info.file_type_name = _kind(kind)
    info.load_commands = ncmds
    if ncmds > 100_000 or sizeofcmds > info.file_size:
        raise MachOError("Invalid load-command table size")
    stream.seek(base_offset + header_size)
    commands = stream.read(sizeofcmds)
    cursor = 0
    for _ in range(ncmds):
        if cursor + 8 > len(commands):
            info.notes.append("Truncated load-command table")
            break
        cmd, cmdsize = struct.unpack_from(endian + "II", commands, cursor)
        if cmdsize < 8 or cursor + cmdsize > len(commands):
            info.notes.append("Invalid load-command size")
            break
        if cmd == LC_CODE_SIGNATURE:
            info.has_code_signature = True
        if cmd in DYLIB_COMMANDS and cmdsize >= 24 and cmd != 0xD:
            nameoff = struct.unpack_from(endian + "I", commands, cursor + 8)[0]
            name = _cstring(commands[cursor:cursor + cmdsize], nameoff)
            if name and name not in info.linked_libraries:
                info.linked_libraries.append(name)
        cursor += cmdsize
