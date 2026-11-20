"""Portable ELF checks, no execution and no requirement for Windows binutils."""
from pathlib import Path
from tpp06_tuya_cutter import sha256_file


def inspect(path):
    from tpp06_assistant_core import AssistantError
    try:
        from elftools.elf.elffile import ELFFile
    except ImportError:
        raise AssistantError("Installer les dépendances de l’assistant sur le PC (pyelftools manquant).") from None
    path = Path(path)
    if not path.is_file() or not 52 <= path.stat().st_size <= 128 * 1024 * 1024:
        raise AssistantError("Programme ELF absent ou taille non prise en charge.")
    with path.open("rb") as source:
        elf = ELFFile(source)
        flags = elf.header.e_flags
        if not (elf.elfclass == 32 and elf.little_endian and elf.header.e_machine == "EM_ARM"
                and elf.header.e_type == "ET_EXEC" and flags & 0xff000000 == 0x05000000
                and flags & 0x200 and not flags & 0x400 and elf.header.e_shnum <= 512
                and elf.header.e_phnum <= 128):
            raise AssistantError("ELF ARM32 EABI5 soft-float exécutable requis, pas ESP32/x86/ARMv7.")
        segments = list(elf.iter_segments())
        if any(segment.header.p_type in ("PT_INTERP", "PT_DYNAMIC") for segment in segments):
            raise AssistantError("Programme statique requis.")
        loads = [segment.header for segment in segments if segment.header.p_type == "PT_LOAD"]
        if not loads or not any(p.p_flags & 1 and p.p_vaddr <= elf.header.e_entry < p.p_vaddr + p.p_memsz for p in loads):
            raise AssistantError("Aucun point d’entrée dans un segment exécutable.")
        if any(p.p_filesz > p.p_memsz or p.p_offset + p.p_filesz > path.stat().st_size for p in loads):
            raise AssistantError("Segments ELF tronqués ou invalides.")
        attributes = elf.get_section_by_name(".ARM.attributes")
        if attributes is None:
            raise AssistantError("Attributs ARM absents ; compatibilité non prouvée.")
        architectures = []
        for subsection in attributes.iter_subsections():
            for group in subsection.iter_subsubsections():
                for item in group.iter_attributes():
                    if item.tag == "TAG_CPU_ARCH":
                        architectures.append(item.value)
                    if item.tag in ("TAG_FP_ARCH", "TAG_ABI_VFP_ARGS", "TAG_ABI_HARDFP_USE") and item.value != 0:
                        raise AssistantError("Instructions ou ABI flottantes matérielles non prises en charge.")
        if not architectures or any(value not in (4, 5) for value in architectures):
            raise AssistantError("ARMv5TE / ARMv5TEJ requis.")
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}
