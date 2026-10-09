// Lists functions nothing seems to reach: candidates for new free code regions (docs/code_space.md,
// "Dead game code"). A function is listed when
//   - Ghidra knows no reference to its entry (calls, jumps, data, literal pools, vtables), and
//   - no aligned 32-bit word of .text, .rodata or .data equals its entry (or entry + 1, Thumb), nor
//     points to it as an offset from itself (PREL31: armcc's .init_array of static constructors), and
//   - no word of .text encodes an ARM b / bl / blx to it, even where Ghidra found no code, and
//   - nothing outside its range [entry, next function) refers into the range (switch tables, jumps),
//   - and the instruction before it cannot fall through into it.
// Adjacent dead functions are merged into runs. Output: one line per run, largest first:
//   size start end functions...
// Args: <output file> [minimum run size, default 64]. Run with analyzeHeadless -process -noanalysis -readOnly.
// This is evidence, not proof: confirm the chosen runs in the game (canary probe, docs/code_space.md).
//@category MH4U
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.FlowType;
import ghidra.program.model.symbol.Reference;

public class DeadFunctions extends GhidraScript {
    private long[] words;     // every aligned word of the initialized blocks, sorted
    private long[] relative;  // the address each word points to as an offset from itself (armcc's
                              // .init_array and other PREL31 tables), sorted
    private long[] branches;  // targets of every word of .text that encodes an ARM b / bl / blx, even
                              // where Ghidra found no code, sorted

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        long minimum = args.length > 1 ? Long.decode(args[1]) : 64;
        loadWords();
        List<Function> functions = new ArrayList<>();
        FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
        while (iterator.hasNext()) {
            functions.add(iterator.next());
        }
        Address textEnd = currentProgram.getMemory().getBlock(".text").getEnd();
        List<long[]> runs = new ArrayList<>();  // start, end
        List<String> names = new ArrayList<>();
        for (int i = 0; i < functions.size(); i++) {
            monitor.checkCancelled();
            Function function = functions.get(i);
            Address start = function.getEntryPoint();
            Address end = i + 1 < functions.size() ? functions.get(i + 1).getEntryPoint() : textEnd.add(1);
            if (!isDead(start, end)) {
                continue;
            }
            int last = runs.size() - 1;
            if (last >= 0 && runs.get(last)[1] == start.getOffset()) {
                runs.get(last)[1] = end.getOffset();
                names.set(last, names.get(last) + " " + function.getName());
            } else {
                runs.add(new long[] {start.getOffset(), end.getOffset()});
                names.add(function.getName());
            }
        }
        Integer[] order = new Integer[runs.size()];
        for (int i = 0; i < order.length; i++) {
            order[i] = i;
        }
        Arrays.sort(order, (a, b) -> Long.compare(size(runs.get(b)), size(runs.get(a))));
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i : order) {
                long[] run = runs.get(i);
                if (size(run) >= minimum) {
                    out.printf("%6d 0x%X 0x%X %s%n", size(run), run[0], run[1], names.get(i));
                }
            }
        }
    }

    private static long size(long[] run) {
        return run[1] - run[0];
    }

    private void loadWords() throws Exception {
        Memory memory = currentProgram.getMemory();
        List<long[]> chunks = new ArrayList<>();
        List<long[]> relativeChunks = new ArrayList<>();
        List<Long> branchTargets = new ArrayList<>();
        int count = 0;
        for (MemoryBlock block : memory.getBlocks()) {
            if (!block.isInitialized()) {
                continue;
            }
            byte[] bytes = new byte[(int) block.getSize()];
            block.getBytes(block.getStart(), bytes);
            long[] chunk = new long[bytes.length / 4];
            long[] relativeChunk = new long[bytes.length / 4];
            long base = block.getStart().getOffset();
            for (int i = 0; i + 3 < bytes.length; i += 4) {
                long word = (bytes[i] & 0xFFL) | (bytes[i + 1] & 0xFFL) << 8 | (bytes[i + 2] & 0xFFL) << 16
                        | (bytes[i + 3] & 0xFFL) << 24;
                chunk[i / 4] = word;
                long prel31 = (word & 0x40000000L) != 0 ? (word & 0x7FFFFFFFL) - 0x80000000L : word & 0x7FFFFFFFL;
                relativeChunk[i / 4] = (base + i + prel31) & 0xFFFFFFFFL;
                if (block.isExecute() && (word >>> 25 & 7) == 5) {
                    long offset = (word & 0x800000L) != 0 ? (word & 0xFFFFFFL) - 0x1000000L : word & 0xFFFFFFL;
                    long target = base + i + 8 + offset * 4;
                    if (word >>> 28 == 0xF) {
                        target += (word >>> 24 & 1) * 2;  // blx: H bit, to Thumb
                    }
                    branchTargets.add(target & 0xFFFFFFFFL);
                }
            }
            chunks.add(chunk);
            relativeChunks.add(relativeChunk);
            count += chunk.length;
        }
        words = new long[count];
        int at = 0;
        for (long[] chunk : chunks) {
            System.arraycopy(chunk, 0, words, at, chunk.length);
            at += chunk.length;
        }
        Arrays.sort(words);
        relative = new long[count];
        at = 0;
        for (long[] chunk : relativeChunks) {
            System.arraycopy(chunk, 0, relative, at, chunk.length);
            at += chunk.length;
        }
        Arrays.sort(relative);
        branches = branchTargets.stream().mapToLong(Long::longValue).sorted().toArray();
    }

    private boolean isDead(Address start, Address end) throws Exception {
        long entry = start.getOffset();
        if (currentProgram.getReferenceManager().getReferenceCountTo(start) > 0
                || Arrays.binarySearch(words, entry) >= 0 || Arrays.binarySearch(words, entry | 1) >= 0
                || Arrays.binarySearch(relative, entry) >= 0 || Arrays.binarySearch(relative, entry | 1) >= 0
                || Arrays.binarySearch(branches, entry) >= 0) {
            return false;
        }
        // Nothing outside the range points into it.
        AddressIterator targets = currentProgram.getReferenceManager().getReferenceDestinationIterator(start, true);
        while (targets.hasNext()) {
            Address to = targets.next();
            if (to.compareTo(end) >= 0) {
                break;
            }
            for (Reference ref : getReferencesTo(to)) {
                Address from = ref.getFromAddress();
                if (from.compareTo(start) < 0 || from.compareTo(end) >= 0) {
                    return false;
                }
            }
        }
        // The previous instruction must not fall through into the entry.
        Instruction previous = getInstructionBefore(start);
        if (previous != null && previous.getMaxAddress().add(1).equals(start)) {
            FlowType flow = previous.getFlowType();
            if (!flow.isTerminal() && !(flow.isJump() && flow.isUnConditional())) {
                return false;
            }
        }
        return true;
    }
}
