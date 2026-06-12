# Sightline — Architecture

## 1. Goals & constraints

Build an eyes-free wearable that converts a forward-facing camera into useful
audio, on a Raspberry Pi 5 (4 GB) powered by a battery, worn on an arm strap.
Detection may run off-device "if technical constraints allow."

Design drivers, in priority order:

1. **Safety** — never block the user's ambient hearing; surface obstacles fast.
2. **Eyes-free** — no screen; all I/O is audio + physical buttons.
3. **Low latency** — feedback must track a walking pace.
4. **Graceful degradation** — works offline; a failing module can't brick the device.
5. **Privacy** — keep imagery on-device unless the user explicitly invokes the cloud.

## 2. Hardware topology

```
            ┌───────────────── Arm strap ─────────────────┐
            │                                              │
 Pi Camera ─┤ CSI ribbon                                   │
            │            ┌──────────────┐                  │
            │   ┌────────┤ Raspberry Pi ├── USB/I²S ─→ speaker / bone-conduction
 Power bank ┼─USB-C─────▶│      5       │                  │
            │   GPIO 17 ─┤ (4 GB)       │   GPIO 27        │
            │  [MODE btn]└──────────────┘  [ACTION btn]    │
            └──────────────────────────────────────────────┘
```

Notes that shaped the design:

- **The Pi 5 dropped the analog audio jack.** Audio must go out over USB, an I²S
  HAT, or Bluetooth. All audio code targets an ALSA device name (`config:
  speech.audio_device`) rather than assuming a jack.
- **Bone-conduction output** is the recommended transducer: it preserves
  environmental hearing, which is a safety requirement for this user group.
- **No GPU/NPU by default.** CPU TFLite gives a few FPS at 300×300 — adequate at
  walking speed. The optional Hailo-8L AI Kit is the upgrade path for 30+ FPS.

## 3. Software architecture

A thin shared library (`sightline/`) provides four reusable services; each
capability (`demos/`) is a small loop composed from them; `main.py` supervises.

```
                    ┌───────────────────── main.py ─────────────────────┐
                    │  mode controller: buttons → start/stop subprocess  │
                    └───────────────────────────────────────────────────┘
                                          │ launches
        ┌───────────────┬────────────────┼─────────────────┬───────────────┐
   01 object       02 face          03 text            04 scene        05 obstacle
   detection       recognition      reader (OCR)       describer (VLM)  alerts
        │               │                │                  │               │
        └──────────── shared services (sightline/) ─────────────────────────┘
            Camera        Speaker        AudioCues        Announcer / Detector
        (picamera2 →   (Piper → eSpeak,  (stereo pan +   (throttle + box→phrase,
         opencv)        priority queue)   pitch earcons)   TFLite / Hailo)
```

### Shared services

- **`Camera`** — abstracts Picamera2 (libcamera) with an OpenCV `VideoCapture`
  fallback, always yielding BGR `numpy` frames with configurable rotation/flip
  for however the camera ends up oriented on the strap.
- **`Speaker`** — a background thread drains a **priority queue**, so the vision
  loop never blocks on audio. Piper (small neural TTS, good on a Pi 5) is
  preferred; eSpeak-NG is the zero-setup fallback; high-priority utterances
  flush the queue so a safety warning is heard first.
- **`AudioCues`** — synthesises short stereo tones. **Horizontal position →
  stereo pan**; **proximity → pitch + pip count**. This is the fast,
  pre-attentive channel; it conveys *where/how urgent* without words.
- **`Announcer`** — converts a normalised detection box into a spoken phrase and
  enforces repeat-suppression and a confidence floor so the device informs
  rather than chatters. Direction from box centre-x; rough distance from box
  height (a monocular proxy — see §5).
- **`Detector`** — TFLite SSD-MobileNet behind a `detect()` interface; a Hailo
  backend stub implements the same interface for the AI Kit.

### Why subprocesses for modes

`main.py` runs the selected capability as a child process. This keeps the
controller trivial, isolates faults (a crash in OCR can't take down the device —
`Restart=on-failure` plus per-mode isolation), and lets continuous and on-demand
modes coexist cleanly (on-demand modes block on stdin; ACTION writes a newline).

## 4. On-device vs off-device

| Capability | Placement | Rationale |
|---|---|---|
| Object detection | On-device | Continuous; needs low latency; must work offline; privacy. CPU TFLite is enough at walking pace. |
| Obstacle alerts | On-device | Safety-critical; cloud round-trip latency is unacceptable. |
| Face recognition | On-device | Continuous + privacy-sensitive (biometrics never leave the device). |
| OCR | On-device | Tesseract is fast and offline; good enough for signs/labels. |
| **Scene description** | **Off-device** | A VLM understands context, layout and relationships far beyond a 6 MB detector. On-demand (button press) bounds latency, cost and data egress. |

The off-device path uses Claude with a single camera frame. The frame is
downscaled before upload (`scene.max_image_edge`) to cut tokens and bandwidth.
The system prompt constrains output to 2–4 short, spoken, navigation-relevant
sentences with no preamble — appropriate for TTS — and thinking is disabled for
snappiness. The response is **streamed and spoken sentence-by-sentence** so the
user hears the first sentence while the rest is still generating. Model is
configurable (`scene.model`): Opus for the richest description, or
Sonnet/Haiku to trade detail for latency and cost.

## 5. Known limitations & upgrade paths

- **Monocular "distance" is a proxy** from bounding-box height — it's coarse and
  class-dependent. The clean upgrade is a real depth source: a VL53L5CX
  time-of-flight sensor over I²C, or a depth model on the AI Kit.
  `announcer.estimate_distance_m` is the single call site to replace.
- **CPU detection is a few FPS.** Fine for walking, marginal for fast motion;
  the Hailo-8L backend (stub provided) lifts this to 30+ FPS.
- **dlib face recognition is heavy on CPU.** Demo 2 already downscales and
  processes every Nth frame; for many enrolled faces, consider MediaPipe or an
  on-NPU embedder.
- **No wake-word / voice input.** Interaction is button-driven. A future "what's
  in front of me?" voice command would pair naturally with the scene describer.
- **Power/thermals** aren't managed here. A real build wants a low-power idle and
  a thermal check; the Pi 5 can throttle under sustained inference.

## 6. Extending

Add a capability by writing a `demos/NN_x.py` that composes `Camera`,
`Speaker`, `AudioCues`, and (optionally) `Detector`/`Announcer`, then add a row
to `MODES` in `main.py`. The shared services are the contract; nothing else
needs to change.
