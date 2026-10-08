// Finds ASCII strings matching a regular expression (ignoring case) anywhere in memory (defined or not) and lists the
// references to each one, with the function they come from.
// Args: <output file> <regex>... (e.g. bgm_ stq; avoid | ( ) in them: analyzeHeadless.bat is a cmd script)
//@category MH4U
import java.io.PrintWriter;
import java.util.regex.Pattern;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

public class Strings extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Pattern[] patterns = new Pattern[args.length - 1];
        for (int i = 1; i < args.length; i++) {
            patterns[i - 1] = Pattern.compile(args[i], Pattern.CASE_INSENSITIVE);
        }
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                if (!block.isInitialized()) {
                    continue;
                }
                byte[] bytes = new byte[(int) block.getSize()];
                block.getBytes(block.getStart(), bytes);
                int start = -1;
                for (int i = 0; i <= bytes.length; i++) {
                    boolean printable = i < bytes.length && bytes[i] >= 0x20 && bytes[i] < 0x7F;
                    if (printable && start < 0) {
                        start = i;
                    } else if (!printable && start >= 0) {
                        if (i - start >= 4 && i < bytes.length && bytes[i] == 0) {
                            report(out, patterns, block.getStart().add(start), new String(bytes, start, i - start, "US-ASCII"));
                        }
                        start = -1;
                    }
                }
            }
        }
    }

    private void report(PrintWriter out, Pattern[] patterns, Address at, String text) {
        for (Pattern pattern : patterns) {
            if (pattern.matcher(text).find()) {
                out.println(at + " \"" + text + "\"");
                for (Reference ref : getReferencesTo(at)) {
                    Function function = getFunctionContaining(ref.getFromAddress());
                    out.println("    <- " + ref.getFromAddress() + " " + (function == null ? "-" : function.getName()));
                }
                return;
            }
        }
    }
}
