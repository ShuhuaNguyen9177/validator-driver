import os
from dataclasses import dataclass


@dataclass
class SymlinkResult:
    exists: bool
    final_target: str
    circular: bool
    depth_exceeded: bool
    hops: int
    resolved_path: str


def _path_startswith(parent: str, child: str) -> bool:
    parent_norm = os.path.normpath(os.path.abspath(parent))
    child_norm = os.path.normpath(os.path.abspath(child))
    if parent_norm == child_norm:
        return True
    return child_norm.startswith(parent_norm + os.sep)


def validate_symlink(path: str, max_depth: int = 40) -> SymlinkResult:
    """Resolve a symlink chain and report its status.

    Returns a SymlinkResult describing whether the final target exists, the
    chain is circular, or the chain exceeds max_depth hops.

    Interpretation chosen (documented in README):
      - max_depth is the maximum number of *symlink hops* permitted. A real
        file or directory reachable in <= max_depth hops is valid. Reaching
        max_depth hops and still pointing at a symlink is a depth_exceeded
        error.
      - circular: we detect a cycle by tracking the set of intermediate
        symlink absolute paths visited. If we revisit one, we stop and report
        circular=True, exists=False.
      - On systems where os.path.islink raises OSError (broken symlink whose
        own stat fails, or permission errors on a parent dir), we report
        exists=False for that link and stop.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    visited: set[str] = set()
    current = path
    hops = 0
    last_link_target = current

    while True:
        # If the current path is not a symlink, resolution ends here.
        try:
            is_link = os.path.islink(current)
        except OSError:
            # Parent directory unreadable or similar; cannot resolve further.
            return SymlinkResult(
                exists=False,
                final_target=os.path.abspath(current),
                circular=False,
                depth_exceeded=False,
                hops=hops,
                resolved_path=os.path.abspath(current),
            )

        if not is_link:
            # Not a symlink: existence is determined by os.path.exists.
            try:
                exists = os.path.exists(current)
            except OSError:
                exists = False
            return SymlinkResult(
                exists=exists,
                final_target=os.path.abspath(current),
                circular=False,
                depth_exceeded=False,
                hops=hops,
                resolved_path=os.path.abspath(current),
            )

        # current is a symlink; we are about to hop.
        if hops >= max_depth:
            # We have already made max_depth hops and are still at a symlink.
            return SymlinkResult(
                exists=False,
                final_target=os.path.abspath(current),
                circular=False,
                depth_exceeded=True,
                hops=hops,
                resolved_path=os.path.abspath(current),
            )

        current_abs = os.path.abspath(current)

        # Cycle detection: if we've seen this exact symlink path before, stop.
        if current_abs in visited:
            return SymlinkResult(
                exists=False,
                final_target=current_abs,
                circular=True,
                depth_exceeded=False,
                hops=hops,
                resolved_path=current_abs,
            )
        visited.add(current_abs)

        # Read the link target. If this raises, the link is unreadable.
        try:
            target = os.readlink(current)
        except OSError:
            return SymlinkResult(
                exists=False,
                final_target=current_abs,
                circular=False,
                depth_exceeded=False,
                hops=hops,
                resolved_path=current_abs,
            )

        # Resolve relative target against the link's directory.
        if not os.path.isabs(target):
            link_dir = os.path.dirname(current_abs)
            next_path = os.path.normpath(os.path.join(link_dir, target))
        else:
            next_path = os.path.normpath(target)

        last_link_target = next_path
        hops += 1
        current = next_path
