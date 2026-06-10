#!/usr/bin/env python3
"""
Fully commented Raspberry Pi 5 diagnostic script.
This script gathers system information using Python and Linux commands.
"""

import os
import platform
import subprocess
import shutil

# Helper function to run shell commands safely
def run(cmd):
    """
    Runs a shell command and returns its output as text.
    If the command fails, returns a friendly message instead of crashing.
    """
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except:
        return "Command failed or not available"


print("=======================================")
print(" Raspberry Pi 5 Diagnostic Report (Python)")
print("=======================================\n")


# ---------------------------------------------------------
# SYSTEM INFORMATION
# ---------------------------------------------------------
print("[SYSTEM INFO]")

# Hostname of the device
print("Hostname:", run("hostname"))

# Raspberry Pi model (Pi 5, RAM size, etc.)
# /proc/device-tree/model contains the hardware model string
print("Model:", run("tr -d '\\0' < /proc/device-tree/model"))

# OS version (e.g., Raspberry Pi OS Bookworm)
print("OS:", run("lsb_release -ds"))

# Linux kernel version
print("Kernel:", platform.release())

# Human‑readable uptime (e.g., "up 2 hours, 5 minutes")
print("Uptime:", run("uptime -p"))
print()


# ---------------------------------------------------------
# CPU INFORMATION
# ---------------------------------------------------------
print("[CPU]")

# CPU model, current speed, min/max frequencies
print(run("lscpu | grep -E 'Model name|CPU MHz|CPU max MHz|CPU min MHz'"))

# CPU temperature using Raspberry Pi firmware tool
print("Temperature:", run("vcgencmd measure_temp"))

# CPU load averages (1, 5, 15 minutes)
print("Load averages:", run("uptime | awk -F'load average:' '{ print $2 }'"))
print()


# ---------------------------------------------------------
# MEMORY INFORMATION
# ---------------------------------------------------------
print("[MEMORY]")

# Shows total, used, and free RAM
print(run("free -h"))
print()


# ---------------------------------------------------------
# DISK INFORMATION
# ---------------------------------------------------------
print("[DISK]")

# Disk usage for the root filesystem
print("Disk usage:")
print(run("df -h /"))
print()

# Disk write speed test
# Writes a 100MB file directly to disk to measure write performance
print("Disk write speed test:")
speed = run("dd if=/dev/zero of=./testfile bs=100M count=1 oflag=direct 2>&1 | grep copied")
print(speed)

# Clean up the test file
run("rm -f testfile")
print()


# ---------------------------------------------------------
# NETWORK INFORMATION
# ---------------------------------------------------------
print("[NETWORK]")

# Shows local IP addresses
print("IP Address:", run("hostname -I"))
print()

# Ping test to verify internet connectivity
print("Ping test:")
print(run("ping -c 4 raspberrypi.com"))
print()

# Optional: speedtest-cli if installed
if shutil.which("speedtest"):
    print("Speedtest:")
    print(run("speedtest --simple"))
else:
    print("Speedtest not installed (sudo apt install speedtest-cli)")
print()


# ---------------------------------------------------------
# GPU INFORMATION
# ---------------------------------------------------------
print("[GPU]")

# GPU memory split (how much RAM is allocated to the GPU)
print("GPU Memory:", run("vcgencmd get_mem gpu"))

# LCD/display info (may not work on HDMI monitors)
print("LCD Info:", run("vcgencmd get_lcd_info"))
print()


# ---------------------------------------------------------
# END OF REPORT
# ---------------------------------------------------------
print("=======================================")
print(" Diagnostics Complete")
print("=======================================")
