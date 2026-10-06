// Lists the references to the given addresses and the function each one comes from.
// Args: <output file> <address>... (e.g. 0xEFE1C4). Run with analyzeHeadless -process -noanalysis -postScript.
//@category MH4U
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class Xrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Address target = toAddr(Long.decode(args[i]));
                out.println("== " + target);
                for (Reference ref : getReferencesTo(target)) {
                    Address from = ref.getFromAddress();
                    Function function = getFunctionContaining(from);
                    out.println("  " + from + " " + ref.getReferenceType() + " "
                            + (function == null ? "-" : function.getName() + " @ " + function.getEntryPoint()));
                }
            }
        }
    }
}
