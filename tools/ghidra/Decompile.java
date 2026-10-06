// Writes the decompiled C of the functions containing the given addresses.
// Args: <output file> <address>... Run with analyzeHeadless -process -noanalysis -postScript.
//@category MH4U
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

public class Decompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Function function = getFunctionContaining(toAddr(Long.decode(args[i])));
                if (function == null) {
                    out.println("// no function at " + args[i]);
                    continue;
                }
                DecompileResults result = decompiler.decompileFunction(function, 180, monitor);
                out.println("// ===== " + function.getName() + " @ " + function.getEntryPoint()
                        + " (asked: " + args[i] + ")");
                out.println(result.decompileCompleted() ? result.getDecompiledFunction().getC()
                        : "// failed: " + result.getErrorMessage());
            }
        } finally {
            decompiler.dispose();
        }
    }
}
