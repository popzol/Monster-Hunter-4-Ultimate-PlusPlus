// Writes the instructions of the functions containing the given addresses, with the value of every
// 4-byte constant they load (as float and hex). Args: <output file> <address>...
//@category MH4U
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.Reference;

public class Listing extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Function function = getFunctionContaining(toAddr(Long.decode(args[i])));
                if (function == null) {
                    out.println("// no function at " + args[i]);
                    continue;
                }
                out.println("// ===== " + function.getName() + " @ " + function.getEntryPoint());
                for (Instruction instruction : currentProgram.getListing().getInstructions(function.getBody(), true)) {
                    StringBuilder line = new StringBuilder();
                    line.append(instruction.getAddress()).append("  ").append(instruction);
                    for (Reference ref : instruction.getReferencesFrom()) {
                        Address to = ref.getToAddress();
                        if (ref.getReferenceType().isRead() && to.isMemoryAddress()) {
                            try {
                                int raw = getInt(to);
                                line.append(String.format("   ; [%s] = 0x%08x (%g)", to, raw, Float.intBitsToFloat(raw)));
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
