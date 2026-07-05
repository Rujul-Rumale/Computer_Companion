"""
seed_memory.py - Populate memory DB with example data.
Run once: python seed_memory.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory import add_person, add_project, init_db, set_fact


def seed():
    init_db()

    # Projects
    add_project(
        "UAV Flight Controller",
        "Custom FC based on STM32F4, PX4-compatible, targeting 250mm racing frame",
        status="active",
        notes="Currently debugging IMU fusion drift at high throttle. ESC protocol: DSHOT300."
    )
    add_project(
        "SDR Scanner",
        "Wideband RF scanner using RTL-SDR v3 + SDR++, Python automation for band logging",
        status="active",
        notes="Coverage: 24MHz - 1.7GHz. Targeting airport ATIS and ACARS decoding."
    )
    add_project(
        "KiCad Power Supply PCB",
        "Dual-rail ±12V bench PSU, LT3080 LDO, current limiting, 3A per rail",
        status="active",
        notes="Rev1 done. Need to check thermal pad via stitching and bulk cap placement."
    )

    # Facts
    set_fact("hardware", "primary_mcu", "STM32F4 (Cortex-M4F, 168MHz)")
    set_fact("hardware", "primary_fpga", "iCE40 LP1K (IceStudio / Yosys)")
    set_fact("software", "preferred_ide", "VS Code + PlatformIO")
    set_fact("software", "preferred_language", "C/C++ for firmware, Python for tooling")
    set_fact("preferences", "response_style", "concise, technical, no padding")
    set_fact("preferences", "explanation_level", "expert — skip basics")
    set_fact("goals", "short_term", "Complete UAV FC rev2 with GPS hold mode")
    set_fact("goals", "long_term", "Build custom radio telemetry link on 915MHz LoRa")
    set_fact("context", "ieee_member", "IEEE Student Member — Communications, AP, CAS societies")
    set_fact("context", "location", "Hyderabad, India")

    # People (optional)
    add_person("Prof. Ramesh", "Project supervisor", "Oversees UAV project. Strict on documentation.")

    print("Memory seeded successfully.")
    print("DB location: data/memory.db")

if __name__ == "__main__":
    seed()
