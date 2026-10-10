"""Hardware detection for GPU, RAM, and CPU."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache

import psutil


@dataclass(frozen=True)
class HardwareProfile:
    gpu_name: str
    gpu_vram_mb: int
    gpu_driver: str
    has_cuda: bool
    ram_gb: int
    cpu_cores: int

    @property
    def vram_tier(self) -> str:
        if self.gpu_vram_mb < 4000:
            return "low"
        if self.gpu_vram_mb < 8000:
            return "medium"
        if self.gpu_vram_mb < 16000:
            return "high"
        return "ultra"


def _detect_gpu() -> tuple[str, int, str, bool]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
        )
        line = out.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        name = parts[0]
        vram_mb = int(parts[1])
        driver = parts[2]
        return name, vram_mb, driver, True
    except Exception:
        return "None", 0, "N/A", False


@lru_cache(maxsize=1)
def detect_hardware() -> HardwareProfile:
    gpu_name, vram_mb, driver, has_cuda = _detect_gpu()
    ram = psutil.virtual_memory()
    ram_gb = round(ram.total / (1024**3))
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 4
    return HardwareProfile(
        gpu_name=gpu_name,
        gpu_vram_mb=vram_mb,
        gpu_driver=driver,
        has_cuda=has_cuda,
        ram_gb=ram_gb,
        cpu_cores=cpu_cores,
    )
