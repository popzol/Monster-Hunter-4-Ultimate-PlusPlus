// Lists the instructions that put one of the given constants in a register: as an immediate operand
// (mov, movw, cmp, add ...) or as a literal-pool word they load. Each line: address, function,
// instruction, how the constant appears. Args: <output file> <value>... (e.g. 0x134)
//@category MH4U
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Set;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.Reference;

public class Scalars extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Set<Long> values = new HashSet<>();
        for (int i = 1; i < args.length; i++) {
            values.add(Long.decode(args[i]));
        }
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (Instruction instruction : currentProgram.getListing().getInstructions(true)) {
                String how = null;
                for (int op = 0; op < instruction.getNumOperands() && how == null; op++) {
                    for (Object object : instruction.getOpObjects(op)) {
                        if (object instanceof Scalar && values.contains(((Scalar) object).getUnsignedValue())) {
                            how = String.format("imm 0x%x", ((Scalar) object).getUnsignedValue());
                            break;
                        }
                    }
                }
                if (how == null) {
                    for (Reference ref : instruction.getReferencesFrom()) {
                        Address to = ref.getToAddress();
                        if (!ref.getReferenceType().isRead() || !to.isMemoryAddress()) {
                            continue;
                        }
                        try {
                            long raw = getInt(to) & 0xFFFFFFFFL;
                            if (values.contains(raw)) {
                                how = String.format("literal [%s] = 0x%x", to, raw);
                                break;
                            }
                        } catch (MemoryAccessException e) {
                            // not loaded memory
                        }
                    }
                }
                if (how != null) {
                    Function function = getFunctionContaining(instruction.getAddress());
                    out.println(instruction.getAddress() + "  " + (function == null ? "-" : function.getName())
                            + "  " + instruction + "   ; " + how);
                }
            }
        }
    }
}
