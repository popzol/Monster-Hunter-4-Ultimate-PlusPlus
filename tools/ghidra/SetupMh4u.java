// Prepares a raw MH4U code.bin loaded at 0x100000 (BinaryLoader, ARM:LE:32:v6) before auto-analysis:
// splits it into .text / .rodata / .data with their permissions, adds .bss, the entry point and
// turns on the aggressive ARM instruction finder. Segment layout of the EUR update (0004000E00126100):
// see docs/hud_layout.md, "Executable". Run with analyzeHeadless -preScript SetupMh4u.java.
//@category MH4U
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;

public class SetupMh4u extends GhidraScript {
    static final long TEXT = 0x100000L;
    static final long RODATA = 0xDED000L;
    static final long DATA = 0xEC0000L;
    static final long DATA_SIZE = 0x1C1B84L;  // bss starts right after it
    static final long BSS_SIZE = 0x9B5A4L;

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        memory.split(memory.getBlock(toAddr(TEXT)), toAddr(RODATA));
        memory.split(memory.getBlock(toAddr(RODATA)), toAddr(DATA));
        configure(memory.getBlock(toAddr(TEXT)), ".text", true, false, true);
        configure(memory.getBlock(toAddr(RODATA)), ".rodata", true, false, false);
        MemoryBlock data = memory.getBlock(toAddr(DATA));
        configure(data, ".data", true, true, false);
        long loadedEnd = DATA + data.getSize();
        long bssEnd = DATA + DATA_SIZE + BSS_SIZE;
        if (bssEnd > loadedEnd) {
            MemoryBlock bss = memory.createUninitializedBlock(".bss", toAddr(loadedEnd), bssEnd - loadedEnd, false);
            configure(bss, ".bss", true, true, false);
        }
        addEntryPoint(toAddr(TEXT));
        createFunction(toAddr(TEXT), "_start");
        setAnalysisOption(currentProgram, "ARM Aggressive Instruction Finder", "true");
    }

    private void configure(MemoryBlock block, String name, boolean read, boolean write, boolean execute)
            throws Exception {
        block.setName(name);
        block.setPermissions(read, write, execute);
    }
}
