#!/usr/bin/env python3
"""
Raspberry Pi Camera Test Script
Works on Raspberry Pi OS (Bookworm) using libcamera.
This script:
1. Checks if the camera is detected
2. Captures a test image
3. Reports success or failure
"""

import subprocess
import time
import os

def run(cmd):
    """Run a shell command and return its output or an error message."""
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return None


print("=======================================")
print(" Raspberry Pi Camera Test (Python)")
print("=======================================\n")

# ---------------------------------------------------------
# STEP 1 — CHECK IF CAMERA IS DETECTED
# ---------------------------------------------------------
print("[CHECKING CAMERA CONNECTION]")

camera_list = run("libcamera-hello --list-cameras")

if camera_list is None or "Available cameras" not in camera_list:
    print("❌ No camera detected by libcamera.")
    print("Make sure:")
    print(" - The camera is connected to the correct CSI port")
    print(" - The ribbon cable is fully seated")
    print(" - You rebooted after connecting the camera")
    exit(1)

print("✅ Camera detected:")
print(camera_list)
print()


# ---------------------------------------------------------
# STEP 2 — CAPTURE A TEST IMAGE
# ---------------------------------------------------------
print("[CAPTURING TEST IMAGE]")

output_file = "camera_test.jpg"

# libcamera-still takes a picture and saves it
result = run(f"libcamera-still -o {output_file} -n --timeout 1000")

if result is None:
    print("❌ Failed to capture image.")
    print("Try running: libcamera-still -o test.jpg")
    exit(1)

# Check if file was created
if os.path.exists(output_file):
    print(f"✅ Test image saved as: {output_file}")
else:
    print("❌ Image file was not created.")
    exit(1)

print()


# ---------------------------------------------------------
# STEP 3 — FINAL RESULT
# ---------------------------------------------------------
print("=======================================")
print(" Camera Test Complete")
print("=======================================")
print("If you see 'camera_test.jpg' in your folder, the camera works.")
