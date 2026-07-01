# Waggle MCP Issues

## 🐛 Bugs

### 1. Memory Leak in AsyncMemoryOrchestrator (Unbounded Set)

**Title:** `[bug] Memory leak in AsyncMemoryOrchestrator — _known_turn_ids grows unboundedly`

**Summary:**
`AsyncMemoryOrchestrator` tracks processed conversation turns in `self._known_turn_ids`, which is an unbounded `set[str]` (`src/waggle/orchestrator.py`, line 185). Every call to `on_assistant_turn()` adds a SHA-256 hash to this set, but entries are never evicted. In a long-running MCP server processing thousands of turns, this causes continuous memory growth proportional to the number of turns processed, constituting a memory leak.

**Steps to reproduce:**
1. Install Waggle from PyPI: `pip install waggle-mcp`
2. Install the VS Code extension: [waggle-memory](https://marketplace.visualstudio.com/items?itemName=Abhigyan-Shekhar.waggle-memory)
3. Run the reproduction script included in the repo: `python reproduce_mem_leak.py`
4. Observe memory usage growing linearly from ~41 MB to ~117 MB over 200,000 turns.

**Expected behavior:**
Memory usage should stabilize after processing turns, using a bounded data structure (e.g., `collections.OrderedDict` with a maxlen eviction policy or TTL-based pruning) to cap the size of `_known_turn_ids`.

**Actual behavior:**
The `set[str]` grows indefinitely. After 200,000 turns, it holds 200,000 SHA-256 hex strings (~12.8 MB of string data alone) and process RSS has grown by ~76 MB.

**Waggle version:** 0.0.1

**Install method:** pip

**Environment:**
Windows 11 Pro, Python 3.11, VS Code with Waggle extension, `WAGGLE_MODEL=deterministic`

**Operating System:** Windows

**Windows-specific details:**
PowerShell 7.4, execution policy RemoteSigned, Windows Terminal

**Screenshot:**
*(Attach the terminal screenshot showing memory growth output from `reproduce_mem_leak.py`)*

**Logs:**
```
Initial Memory: 41.04 MB
After 50000 turns: 59.36 MB
After 100000 turns: 78.30 MB
After 150000 turns: 95.64 MB
Final Memory: 116.77 MB
Set size: 200000
```

---

### 2. Redundant Duplicate Subqueries in Ablation Mode

**Title:** `[bug] Random ablation subqueries produce duplicates causing redundant graph retrievals`

**Summary:**
In `src/waggle/recursive_context.py` (lines 227–247), when the `random_subqueries` ablation flag is set, the random slicer generates word slices from the query. However, it does not track which substrings have already been generated. For short queries (e.g., 2 words like "Fix issue"), the only possible 2-word slice is the entire query, so all `max_subqueries` entries are identical. Each duplicate triggers a separate graph retrieval call, wasting compute.

**Steps to reproduce:**
1. Install Waggle from PyPI: `pip install waggle-mcp`
2. Install the VS Code extension: [waggle-memory](https://marketplace.visualstudio.com/items?itemName=Abhigyan-Shekhar.waggle-memory)
3. Create and run the reproduction script `reproduce_dup_subqueries.py`:
   ```python
   import random
   query = "Fix issue"
   words = query.split()
   max_subqueries = 6
   rng = random.Random(42)
   subqueries = []
   attempts = 0
   while len(subqueries) < max_subqueries and attempts < max_subqueries * 10:
       attempts += 1
       if len(words) < 2:
           break
       slice_len = rng.randint(2, min(4, len(words)))
       start = rng.randint(0, len(words) - slice_len)
       substring = " ".join(words[start:start + slice_len])
       subqueries.append(substring)
   print(f"Generated {len(subqueries)} subqueries:")
   for i, sq in enumerate(subqueries, 1):
       print(f"  {i}. '{sq}'")
   unique = set(subqueries)
   print(f"Unique: {len(unique)}, Duplicates: {len(subqueries) - len(unique)}")
   ```
4. Observe that all 6 subqueries are identical `"Fix issue"`.

**Expected behavior:**
The `while` loop should track unique substrings using a `set` and only append genuinely distinct subqueries, or break early when the possible unique slices are exhausted.

**Actual behavior:**
All 6 generated subqueries are the same string `"Fix issue"`, causing 6 identical graph retrieval calls instead of 1.

**Waggle version:** 0.0.1

**Install method:** pip

**Environment:**
Windows 11 Pro, Python 3.11, VS Code with Waggle extension

**Operating System:** Windows

**Windows-specific details:**
PowerShell 7.4, execution policy RemoteSigned, Windows Terminal

**Screenshot:**
*(Attach the terminal screenshot showing all 6 subqueries are identical)*

**Logs:**
```
Query: 'Fix issue'
Words: ['Fix', 'issue']
Generated 6 subqueries:
  1. 'Fix issue'
  2. 'Fix issue'
  3. 'Fix issue'
  4. 'Fix issue'
  5. 'Fix issue'
  6. 'Fix issue'

Unique subqueries: 1
Duplicate subqueries: 5

This means 5 redundant graph retrievals!
```

---

### 3. Argument Injection via Shell Splitting in rlm.py (CWE-88)

**Title:** `[bug] Argument injection via shlex.split after str.format in build_subprocess_response_fn`

**Summary:**
In `src/waggle/rlm.py` (lines 180–199), the function `build_subprocess_response_fn` formats a user-controlled prompt string directly into a command template using `str.format()`, then parses the result with `shlex.split()`. Because shell splitting runs after string interpolation, a crafted prompt containing shell metacharacters (e.g., `hello" --malicious-flag "payload`) causes the injected flags to be parsed as separate command-line arguments, constituting CWE-88 (Argument Injection).

**Steps to reproduce:**
1. Install Waggle from PyPI: `pip install waggle-mcp`
2. Install the VS Code extension: [waggle-memory](https://marketplace.visualstudio.com/items?itemName=Abhigyan-Shekhar.waggle-memory)
3. Run the reproduction script `reproduce_arg_injection.py`:
   ```python
   import shlex
   command_template = 'llm --prompt "{prompt}" --output result.txt'
   normal = "Hello world"
   malicious = 'hello" --malicious-flag "payload'
   cmd_normal = command_template.format(prompt_file="tmp/prompt.txt", prompt=normal)
   cmd_malicious = command_template.format(prompt_file="tmp/prompt.txt", prompt=malicious)
   print(f"Normal args:    {shlex.split(cmd_normal)}")
   print(f"Malicious args: {shlex.split(cmd_malicious)}")
   ```
4. Observe that the malicious prompt injects `--malicious-flag` as a separate argument.

**Expected behavior:**
The command template should use `shlex.split()` first to produce an argument list, then replace the `{prompt}` placeholder within the list without re-splitting. Alternatively, only the safe `{prompt_file}` path parameter should be used.

**Actual behavior:**
User input is interpreted as additional command-line arguments by `shlex.split`, resulting in argument injection.

**Waggle version:** 0.0.1

**Install method:** pip

**Environment:**
Windows 11 Pro, Python 3.11, VS Code with Waggle extension

**Operating System:** Windows

**Windows-specific details:**
PowerShell 7.4, execution policy RemoteSigned, Windows Terminal

**Screenshot:**
*(Attach the terminal screenshot showing normal (5 args) vs malicious (7 args) output)*

**Logs:**
```
=== NORMAL PROMPT ===
Command string: llm --prompt "Hello world" --output result.txt
Parsed args:    ['llm', '--prompt', 'Hello world', '--output', 'result.txt']
Arg count:      5

=== MALICIOUS PROMPT ===
Command string: llm --prompt "hello" --malicious-flag "payload" --output result.txt
Parsed args:    ['llm', '--prompt', 'hello', '--malicious-flag', 'payload', '--output', 'result.txt']
Arg count:      7

⚠️  Notice: the malicious prompt injected '--malicious-flag' as a
   separate argument, which would be passed to the subprocess!
```

---

### 4. Potential Zip Bomb Risk on .abhi Imports (CWE-409)

**Title:** `[bug] No uncompressed-size limit in _read_member allows zip bomb DoS on .abhi import`

**Summary:**
In `src/waggle/abhi.py` (line 227), the function `_read_member` calls `archive.read(member_name)` to load the entire decompressed ZIP member into RAM without checking the uncompressed size first. The companion `_write_member` function (line 244) records `"size": len(payload)` in the manifest metadata, but `_read_member` never reads or enforces this field. A maliciously crafted `.abhi` file with a high compression ratio (zip bomb) could cause an out-of-memory crash when the server attempts to decompress the payload.

**Steps to reproduce:**
1. Install Waggle from PyPI: `pip install waggle-mcp`
2. Install the VS Code extension: [waggle-memory](https://marketplace.visualstudio.com/items?itemName=Abhigyan-Shekhar.waggle-memory)
3. Open `src/waggle/abhi.py` and inspect lines 223–231:
   ```python
   def _read_member(archive, manifest, member_name, *, passphrase):
       metadata = dict(manifest.get("members", {}).get(member_name, {}))
       if member_name not in archive.namelist():
           return b""
       raw = archive.read(member_name)  # ← No size check before full decompression
   ```
4. Compare with `_write_member` at lines 242–244 which records `"size"` but `_read_member` never checks it.

**Expected behavior:**
`_read_member` should check `metadata.get("size")` against a safety ceiling (e.g., 100 MB) before calling `archive.read()`, or stream the member in bounded chunks and abort if the uncompressed output exceeds the limit.

**Actual behavior:**
The entire decompressed payload is loaded into RAM without any size validation.

**Waggle version:** 0.0.1

**Install method:** pip

**Environment:**
Windows 11 Pro, Python 3.11, VS Code with Waggle extension

**Operating System:** Windows

**Windows-specific details:**
PowerShell 7.4, execution policy RemoteSigned, Windows Terminal

**Screenshot:**
*(Attach a screenshot of abhi.py lines 223–231 showing the missing size check, annotated with the issue)*

**Logs:**
```
# _write_member records size in manifest:
member_meta = {
    "sha256": hashlib.sha256(payload).hexdigest(),
    "size": len(payload),        # ← size IS recorded
    "encrypted": bool(passphrase),
}

# _read_member IGNORES size:
raw = archive.read(member_name)  # ← no check against metadata["size"]
```

---

## 🚀 Feature Requests

### 1. Add `waggle-mcp stats` command for orchestrator memory visibility

**Title:** `[feature] Add waggle-mcp stats command to surface orchestrator memory usage`

**Problem or use case:**
After long-running sessions, operators have no CLI visibility into the `AsyncMemoryOrchestrator`'s internal state — the `_known_turn_ids` set size, queue depth, or policy counters. The existing `waggle-mcp doctor` command checks system health but does not report runtime memory statistics. This makes it difficult to diagnose memory issues, capacity plan, or verify that fixes (like bounding `_known_turn_ids`) are working as expected.

**Proposed solution:**
Add a `waggle-mcp stats` subcommand that reports:
- Current `_known_turn_ids` count and estimated memory footprint
- Ingest queue depth and capacity
- Last ingest timestamps per scope from `MemoryPolicy.last_ingest_at`
- Optionally support `--json` for machine-readable output (consistent with `doctor --json`)

**Alternatives considered:**
- Extending `get_stats` MCP tool — useful for LLMs but not for CLI operators doing system administration
- Adding the stats to `waggle-mcp doctor` — reasonable but `doctor` is diagnostic/fix-focused, whereas `stats` is monitoring-focused

**Suggested implementation scope:**
`src/waggle/server.py` (CLI parser + stats subcommand), `src/waggle/orchestrator.py` (expose stats method), `tests/test_orchestrator.py`

**Screenshot:**
*(Attach a screenshot of `waggle-mcp doctor` output and annotate: "No orchestrator memory stats shown")*

---

## 📖 Documentation Improvements

### 1. Clarify WAGGLE_MODEL=deterministic Degradation

**Title:** `[docs] Clarify that WAGGLE_MODEL=deterministic disables semantic retrieval`

**Documentation gap:**
The README (line 375) describes `WAGGLE_MODEL=deterministic` as having *"slightly lower retrieval quality"*. This significantly understates the impact. Deterministic mode replaces the sentence-transformer embedding model with SHA-256 hash bucketing into a 256-dimensional vector (`src/waggle/embeddings.py`, lines 363–374). This completely disables semantic similarity — "cat" and "feline" produce unrelated vectors. The same misleading phrasing appears in `CONTRIBUTING.md` (line 303). Users may unknowingly deploy this in production, resulting in effectively broken retrieval.

**Relevant page or file:**
`README.md`, `CONTRIBUTING.md`, `docs/environment-variables.md`

**Proposed improvement:**
Replace *"slightly lower retrieval quality"* with a prominent warning such as:
> **⚠️ `WAGGLE_MODEL=deterministic` is for CI/testing only.** It replaces semantic embeddings with SHA-256 hash bucketing, which completely disables semantic similarity. Do not use in production — retrieval quality will be fundamentally degraded.

**Screenshot:**
*(Attach a screenshot of README.md line 375 showing the misleading "slightly lower retrieval quality" text)*

---

### 2. Documenting Multi-Tenant Isolation Guarantees

**Title:** `[docs] Document tenant_id isolation guarantees for multi-tenant deployments`

**Documentation gap:**
The `CONTRIBUTING.md` Scoping/Tenancy table (lines 189–200) lists `tenant_id` as providing "Top-level multi-tenant isolation," but does not explain what isolation guarantees this provides. Developers deploying the Waggle server centrally across multiple users cannot determine whether `tenant_id` provides enforced data separation (row-level security) or merely logical namespace scoping (a WHERE clause filter). This is critical for compliance and security assessments in multi-tenant environments.

**Relevant page or file:**
`CONTRIBUTING.md`, `docs/repository-map.md`, `docs/environment-variables.md`

**Proposed improvement:**
Add a dedicated "Multi-Tenant Isolation" section to the deployment docs that explicitly states:
- Whether isolation is logical (namespace filter) or enforced (row-level security)
- How `tenant_id` is scoped in SQLite vs Neo4j backends
- Any security implications of the current design
- Recommendations for production multi-tenant deployments

**Screenshot:**
*(Attach a screenshot of the CONTRIBUTING.md tenancy table showing "Top-level multi-tenant isolation" without further explanation)*
