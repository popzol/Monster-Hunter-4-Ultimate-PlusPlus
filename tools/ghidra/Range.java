// Writes the instructions between two addresses, even outside any function, with the value of every
// 4-byte constant they load and the name of every function they call.
// Args: <output file> <start> <end> [<start> <end>]...
//@category MH4U
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.Reference;

public class Range extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i + 1 < args.length; i += 2) {
                Address start = toAddr(Long.decode(args[i]));
                Address end = toAddr(Long.decode(args[i + 1]));
                out.println("// ===== " + start + " - " + end);
                for (Instruction instruction : currentProgram.getListing().getInstructions(new AddressSet(start, end), true)) {
                    StringBuilder line = new StringBuilder();
                    Function function = getFunctionAt(instruction.getAddress());
                    if (function != null) {
                        out.println("// --- " + function.getName());
                    }
                    line.append(instruction.getAddress()).append("  ").append(instruction);
                    for (Reference ref : instruction.getReferencesFrom()) {
                        Address to = ref.getToAddress();
                        if (ref.getReferenceType().isRead() && to.isMemoryAddress()) {
                            try {
                                line.append(String.format("   ; [%s] = 0x%08x", to, getInt(to)));
                            } catch (MemoryAccessException e) {
                                line.append("   ; [" + to + "] unreadable");
                            }
                        } else if (ref.getReferenceType().isCall()) {
                            Function callee = getFunctionAt(to);
                            line.append("   ; call ").append(callee == null ? to.toString() : callee.getName());
                        }
                    }
                    out.println(line);
                }
            }
        }
    }
}
