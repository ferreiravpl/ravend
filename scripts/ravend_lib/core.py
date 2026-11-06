"""Identity of the project, where its local data lives, JSON/profile I/O, git helpers, locks and the
tree fingerprint (content hash of the working tree) that every state record is tied to."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no cross-process locks (native Windows is unsupported anyway)
    fcntl = None

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROTECTED = [".env", ".env.local", ".env.*.local", "*.pem", "*.key", "*id_rsa*"]
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".gradle", ".idea", ".vscode", "coverage", ".angular", ".next", "out"}


# --------------------------------------------------------------------------- paths & identity

def ravend_home() -> Path:
    # EVAL_RAVEND_HOME exists only for `claude plugin eval`, which lets cases set EVAL_* variables only.
    home = os.environ.get("RAVEND_HOME") or os.environ.get("EVAL_RAVEND_HOME") or Path.home() / ".ravend"
    return Path(home).expanduser().resolve()


def git(args: list[str], cwd: Path, env: dict | None = None) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def repo_root(cwd: Path) -> Path | None:
    top = git(["rev-parse", "--show-toplevel"], cwd)
    return Path(top) if top else None


def _slug(text: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9._-]+", "-", text.lower())).strip("-.")


def project_id(root: Path) -> str:
    """Stable id shared by every clone/worktree of the same repo: derived from origin, else the git dir."""
    remote = git(["config", "--get", "remote.origin.url"], root)
    if remote:
        r = re.sub(r"^[a-z+]+://", "", remote.strip())
        r = re.sub(r"^[^@/]+@", "", r)
        r = re.sub(r"\.git/?$", "", r).replace(":", "/")
        return _slug(r)
    common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], root) or str(root)
    base = Path(common).parent if common.endswith(".git") else Path(common)
    return f"{_slug(base.name)}-{hashlib.sha1(str(base).encode()).hexdigest()[:8]}"


def data_dir(root: Path) -> Path:
    return ravend_home() / "projects" / project_id(root)


def state_dir(root: Path) -> Path:
    """Gate/app state is per checkout: the main clone and each git worktree get their own, so parallel
    runs on different worktrees never overwrite each other's gate result. Specs/knowledge stay shared."""
    key = f"{_slug(root.name) or 'repo'}-{hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]}"
    return data_dir(root) / "state" / key


@contextmanager
def file_lock(path: Path, blocking: bool = True, wait_msg: str = ""):
    """Exclusive cross-process lock. Yields True when held, False when non-blocking and busy."""
    if fcntl is None:
        yield True
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if not blocking:
                yield False
                return
            if wait_msg:
                print(wait_msg, flush=True)
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def ensure_dirs(d: Path) -> None:
    for sub in ("knowledge", "specs", "runs", "state"):
        try:
            (d / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # read-only home (sandbox/CI): commands that need to write will report it


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_profile(root: Path) -> dict | None:
    return load_json(data_dir(root) / "profile.json")


def base_branch(root: Path, profile: dict | None) -> str:
    configured = ((profile or {}).get("git") or {}).get("base_branch")
    if configured:
        return configured
    head = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root)
    if head:
        return head
    for name in ("main", "master", "develop"):
        if git(["rev-parse", "--verify", "--quiet", name], root):
            return name
    return "HEAD"


# --------------------------------------------------------------------------- changes & fingerprint

def changed_files(root: Path, scope: str, profile: dict | None) -> list[str]:
    files: set[str] = set()
    has_head = git(["rev-parse", "--verify", "--quiet", "HEAD"], root) is not None
    if has_head:
        files.update((git(["diff", "--name-only", "HEAD"], root) or "").splitlines())
    files.update((git(["diff", "--name-only", "--cached"], root) or "").splitlines())
    files.update((git(["ls-files", "--others", "--exclude-standard"], root) or "").splitlines())
    if scope == "branch" and has_head:
        base = base_branch(root, profile)
        mb = git(["merge-base", "HEAD", base], root)
        if mb:
            files.update((git(["diff", "--name-only", mb, "HEAD"], root) or "").splitlines())
    return sorted(f for f in files if f)


def tree_fingerprint(root: Path) -> str | None:
    """Hash of the full working tree content (tracked + untracked, honoring .gitignore).
    Identical content gives the same id whether it is committed or not."""
    index = git(["rev-parse", "--path-format=absolute", "--git-path", "index"], root)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_index = Path(tmp) / "index"
            if index and Path(index).exists():
                shutil.copyfile(index, tmp_index)
            env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
            if git(["add", "-A"], root, env=env) is None:
                return None
            return git(["write-tree"], root, env=env)
    except OSError:  # no writable temp dir (sandboxes): the state machine treats "unknown" as "changed"
        return None


# --------------------------------------------------------------------------- small readers

def _read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out
