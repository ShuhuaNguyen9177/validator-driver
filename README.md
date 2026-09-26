# Symlink Validator

Resolves a symlink chain and reports whether the target exists, the chain is circular, or it exceeds a configurable maximum depth.

## Usage

```python
from symlink_validator import validate_symlink, SymlinkResult

result: SymlinkResult = validate_symlink("/path/to/link", max_depth=40)

print(result.exists)           # bool - does the final target exist?
print(result.circular)         # bool - did the chain revisit a symlink already seen?
print(result.depth_exceeded)   # bool - did we run out of hops before reaching a non-symlink?
print(result.hops)             # int   - number of symlink hops taken
print(result.final_target)     # str   - absolute path of the final resolved target
print(result.resolved_path)    # str   - absolute path where resolution stopped
```

## Why this exists

Symlink chains are a common source of operational surprises: a link points to a link points to a missing file, or two links point at each other and hang tools that naively follow them. This library gives a single function that follows the chain manually (rather than relying on `os.path.realpath` / `os.path.abspath`, which collapse links silently) so you can tell the three failure modes apart.

The deliberate trade-off: `max_depth` counts *symlink hops*, not filesystem path components. A chain that hops through five symlinks to reach a real file is fine; a chain still on a symlink after `max_depth` hops is reported as `depth_exceeded`. This is stricter than counting total path segments and stricter than letting the OS chase an arbitrary chain — both of which make error messages harder to act on.

## Edge cases you will hit

- **Relative symlink targets** are resolved against the *containing directory of the link*, matching POSIX `readlink` semantics. A link `/foo/bar/ln` whose target is `../baz` resolves to `/foo/baz`, not `/baz`.
- **Self-referential links** (`ln -> ln`) and **mutual cycles** (`a -> b -> a`) are detected by tracking the set of absolute symlink paths already visited; on a repeat, `circular=True` and `exists=False`.
- **`max_depth=0`** means "the starting path must not be a symlink." If it is, you get `depth_exceeded=True, hops=0`. A non-symlink at depth 0 is fine.
- **Broken symlinks** (target does not exist) report `exists=False, circular=False, depth_exceeded=False` with `hops=1` — the link itself was followed, the target just isn't there.
- **Permission errors** on a parent directory surface as `exists=False`; the library does not attempt to distinguish "missing" from "unreadable" because `os.path.islink` raises `OSError` for both and we do not catch-and-retry.

Requires Python 3.10+ (uses `set[str]` and `dataclasses`).
