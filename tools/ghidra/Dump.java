// Prints memory as hex words: at each address, or at the address stored there with '*' (a literal
// pool pointer). Args: <output file> <address>[:<count of 16-bit values>]... (e.g. *0x2F93B4:24)
//@category MH4U
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class Dump extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                String spec = args[i];
                int count = 16;
                int colon = spec.indexOf(':');
                if (colon >= 0) {
                    count = Integer.decode(spec.substring(colon + 1));
                    spec = spec.substring(0, colon);
                }
                boolean indirect = spec.startsWith("*");
                Address at = toAddr(Long.decode(indirect ? spec.substring(1) : spec));
                if (indirect) {
                    at = toAddr(getInt(at) & 0xFFFFFFFFL);
                }
                StringBuilder line = new StringBuilder(args[i] + " -> " + at + ":");
                for (int k = 0; k < count; k++) {
                    line.append(String.format(" %04x", getShort(at.add(2L * k)) & 0xFFFF));
                }
                out.println(line);
            }
        }
    }
}
