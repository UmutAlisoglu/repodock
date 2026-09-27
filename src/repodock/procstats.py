"""CPU and memory use of a process and everything it started, without third-party packages.

Linux reads /proc, macOS and other Unixes ask ``ps``, and Windows asks the
kernel through ctypes. CPU is measured between two samples, as a share of the
whole machine (like Task Manager).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass


@dataclass
class Proc:
    pid: int
    ppid: int
    cpu_seconds: float  # user + system time used so far
    rss: int  # resident memory in bytes


def snapshot(roots: list[int] | None = None) -> dict[int, Proc]:
    """Processes this user can see, by pid (on Windows only the trees under ``roots``, when given)."""
    try:
        if sys.platform.startswith("win"):
            return _windows(roots)
        if os.path.isdir("/proc/self"):
            return _linux()
        return _ps()
    except Exception:  # stats are a nice-to-have; never break the dashboard
        return {}


def _linux() -> dict[int, Proc]:
    tick = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    out: dict[int, Proc] = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as fh:
                raw = fh.read().decode("latin-1")
        except OSError:
            continue
        # The command name is in parentheses and may contain spaces.
        fields = raw[raw.rfind(")") + 2:].split()
        try:
            out[int(name)] = Proc(int(name), int(fields[1]), (int(fields[11]) + int(fields[12])) / tick, int(fields[21]) * page)
        except (IndexError, ValueError):
            continue
    return out


def parse_cputime(text: str) -> float:
    """ps TIME: [[dd-]hh:]mm:ss[.ff]"""
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    parts = [float(p) for p in text.split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return days * 86400 + seconds


def _ps() -> dict[int, Proc]:
    res = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,time="], capture_output=True, text=True, timeout=5)
    out: dict[int, Proc] = {}
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            pid, ppid, rss = int(parts[0]), int(parts[1]), int(parts[2]) * 1024
            out[pid] = Proc(pid, ppid, parse_cputime(parts[3]), rss)
        except ValueError:
            continue
    return out


def _windows(roots: list[int] | None = None) -> dict[int, Proc]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return {}
    parents: dict[int, int] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    wanted = set(parents)
    if roots is not None:
        # Opening every process is slow; only measure the trees we were asked about.
        skeleton = {pid: Proc(pid, ppid, 0.0, 0) for pid, ppid in parents.items()}
        wanted = {pid for root in roots for pid in tree(skeleton, root)}
    out: dict[int, Proc] = {}
    for pid, ppid in parents.items():
        if pid not in wanted:
            continue
        cpu, rss = 0.0, 0
        handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
        if handle:
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                if kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                    kernel_t, user_t = times[2], times[3]
                    cpu = ((kernel_t.dwHighDateTime << 32 | kernel_t.dwLowDateTime) + (user_t.dwHighDateTime << 32 | user_t.dwLowDateTime)) / 1e7
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    rss = counters.WorkingSetSize
            finally:
                kernel32.CloseHandle(handle)
        out[pid] = Proc(pid, ppid, cpu, rss)
    return out


def tree(procs: dict[int, Proc], root: int) -> list[int]:
    """root and all of its descendants that are still alive."""
    children: dict[int, list[int]] = {}
    for p in procs.values():
        if p.pid != p.ppid:
            children.setdefault(p.ppid, []).append(p.pid)
    found, todo = [], [root]
    while todo:
        pid = todo.pop()
        if pid in procs and pid not in found:
            found.append(pid)
            todo.extend(children.get(pid, []))
    return found


class Sampler:
    """Remembers the previous sample so CPU can be reported as a percentage."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_time = 0.0
        self.last_cpu: dict[int, float] = {}
        self.cpus = os.cpu_count() or 1
        self.cached: tuple[float, dict[str, int], dict[str, dict]] | None = None

    def measure(self, roots: dict[str, int]) -> dict[str, dict]:
        """{key: pid} -> {key: {"cpu": percent, "rss": bytes, "procs": n}}"""
        if not roots:
            return {}
        with self.lock:
            now = time.monotonic()
            if self.cached and now - self.cached[0] < 1.0 and self.cached[1] == roots:
                return self.cached[2]  # several pages polling at once shouldn't shrink the interval
            procs = snapshot(list(roots.values()))
            elapsed = now - self.last_time if self.last_time else 0.0
            result: dict[str, dict] = {}
            cpu_now: dict[int, float] = {}
            for key, root in roots.items():
                pids = tree(procs, root)
                used = rss = 0.0
                for pid in pids:
                    p = procs[pid]
                    cpu_now[pid] = p.cpu_seconds
                    rss += p.rss
                    if elapsed > 0 and pid in self.last_cpu:
                        used += max(0.0, p.cpu_seconds - self.last_cpu[pid])
                percent = (used / elapsed / self.cpus * 100) if elapsed > 0 else 0.0
                result[key] = {"cpu": round(min(percent, 100.0), 1), "rss": int(rss), "procs": len(pids)}
            self.last_cpu = cpu_now
            self.last_time = now
            self.cached = (now, dict(roots), result)
            return result
