# Sightline architecture

## 1. Goals and constraints

Build an eyes-free wearable that converts a forward-facing camera into useful audio, on a Raspberry Pi 5 (4 GB) powered by a battery and worn on an arm strap. Heavy work may run off-device when the gain is worth it.

The design drivers, in priority order:

1. Safety. Never block the user's ambient hearing, and surface obstacles fast.
2. Eyes-free. No screen is required. All input and output is audio plus physical buttons.
3. Low latency. Feedback has to keep up with a walking pace.
4. Graceful degradation. The device works offline, and a failing module cannot brick it.
5. Privacy. Imagery stays on the device unless the user explicitly invokes the cloud.

## 2. Hardware topology

```
            +------------------ Arm strap ------------------+
            |                                               |
 Pi Camera -+ CSI ribbon                                    |
            |            +--------------+                   |
            |   GPIO 17 -+ Raspberry Pi +-- USB / I2S --> speaker / bone conduction
 Power bank +-- USB-C -->+      5       |                   |
            |   GPIO 27 -+   (4 GB)     |                   |
            | [MODE btn] +--------------+ [ACTION btn]      |
            +-----------------------------------------------+
```

Notes that shaped the design:

- The Pi 5 dropped the analog audio jack. Audio goes out over USB, an I2S HAT, or Bluetooth. All audio code targets an ALSA device name (speech.audio_device) rather than assuming a jack.
- Bone-conduction output is the recommended transducer because it preserves environmental hearing, which is a safety requirement for this user group.
- No GPU or NPU by default. CPU TFLite gives a few frames per second at low resolution, which is adequate at walking speed. The optional Hailo-8L AI Kit is the upgrade path for higher frame rates.

## 3. Software architecture

A thin shared library (sightline/) provides reusable services. Each capability is a small loop composed from those services. Two entry points drive the device.

```
   app.py  (voice assistant, always on)        main.py  (two-button controller)
        |                                            |
        |  wake word + background detection          |  MODE cycles, ACTION captures
        |                                            |  one capability per subprocess
        +--------------------+-----------------------+
                             |
                 shared services (sightline/)
   Camera   Speaker   AudioCues   Announcer   Detector   FaceIdentifier
   OcrReader   SceneDescriber   VisionAssistant   VoiceCommands
```

### Shared services

- Camera abstracts Picamera2 (the libcamera stack on Raspberry Pi OS) with an OpenCV VideoCapture fallback, so the same code runs on the Pi Camera, a laptop webcam, or a recorded clip. It always yields BGR numpy frames with configurable rotation and flip.
- Speaker drains a priority queue on a background thread, so the vision loop never blocks on audio. Piper is preferred for natural speech, eSpeak-NG is the zero-setup fallback, and a plain print path keeps a dev box observable. High-priority utterances flush the queue so a safety warning is heard first. The speaker is thread-safe: rendering is serialised and the running audio process is guarded, so a wake-word barge-in from another thread reliably stops the current utterance and two voices never overlap.
- AudioCues synthesises short stereo tones. Horizontal position maps to stereo pan, and proximity maps to pitch and pip count. This is the fast, pre-attentive channel that tells you where and how urgent without using words.
- Announcer turns a detection box into a spoken phrase and enforces repeat-suppression and a confidence floor, so the device informs rather than chatters. Direction comes from the box centre, and a rough distance comes from the box height. It also owns OBSTACLE_CLASSES, the single shared list of object classes worth warning about.
- Detector runs object detection behind one detect() interface. TFLite SSD-MobileNet is the Pi default, Ultralytics YOLO is the easy path on a laptop, and a Hailo backend stub slots in behind the same interface for the AI Kit.
- FaceIdentifier, OcrReader, SceneDescriber, and VisionAssistant cover faces, text, scene description, and the on-demand vision questions (money, label, translate, expression). The three vision callers share one JPEG encoder in imaging.py, which downscales the frame before upload to save tokens and bandwidth.
- VoiceCommands (listen.py) does offline wake-word and command recognition with Vosk and a constrained grammar.

### The voice assistant (app.py)

This is the production path. One loop reads frames, runs object detection every few frames, and emits optional proximity beeps. In parallel, a Vosk thread listens for "sight" plus a command and pushes recognised commands onto a queue that the loop polls. Commands fall into two groups. Quick ones answer from local state or a single capture. On-demand ones (text, describe, the vision questions) take a frame and call a capability. The instant the wake word is heard, a callback interrupts any current speech and plays a short chime, so the user gets immediate confirmation and can talk over the device. A preview window with clickable buttons and keyboard keys mirrors the main commands as a no-voice fallback.

### The button controller (main.py)

A simpler model that runs one capability at a time. The MODE button cycles through the capabilities and speaks the new one aloud. The ACTION button triggers a single capture in the on-demand modes (text reader and scene describer) and is ignored by the continuous modes. Each capability runs as its own subprocess, which keeps the controller tiny and isolates faults: a crash in one capability cannot take down the device, and the systemd unit can restart it.

main.py adapts to how it is launched. With a terminal it reads single keypresses (m, a, q). Without a terminal, for example under systemd at boot, it starts in headless mode where the GPIO button callbacks drive the modes and the process shuts down cleanly on SIGTERM. This is what makes the on-strap, button-only build boot reliably.

## 4. On-device versus off-device

| Capability | Placement | Reason |
| --- | --- | --- |
| Object detection | On device | Continuous, needs low latency, must work offline, and keeps imagery local. CPU TFLite is enough at walking pace. |
| Obstacle alerts | On device | Safety critical. A cloud round trip is too slow. |
| Face recognition | On device | Continuous and privacy-sensitive. Biometrics never leave the device. |
| OCR | On device or cloud | Tesseract and EasyOCR run offline. Claude vision is used when a key is set, because it is far more accurate on real-world signs and labels. |
| Scene description | Off device | A vision-language model understands context, layout, and relationships well beyond a small on-device detector. It is on-demand, so latency, cost, and data egress stay bounded. |

The off-device path sends a single, downscaled camera frame to Claude. The system prompt constrains the output to short, spoken, navigation-relevant text with no preamble, which suits text-to-speech, and thinking is disabled for speed. The scene reply is streamed so the visible text updates as it arrives. The model is configurable: a larger model for the richest description, or a smaller one to trade detail for latency and cost.

## 5. Concurrency and audio

The vision loop must never stall on audio or recognition, so both run off the main thread. The Speaker owns a background worker and a priority queue. The voice recogniser owns its own capture thread and pushes commands onto a queue the loop polls without blocking.

Because three threads can touch the speaker (the worker, a direct say_blocking call, and a wake-word interrupt), the speaker serialises rendering with one lock and guards the running process handle with another. The locks are ordered so the blocking wait on the audio process is never held under the process lock, which lets an interrupt terminate the current utterance while a render is in progress. One platform note: when the voice app holds the microphone open, audio cues are played through aplay rather than sounddevice, because mixing a transient PortAudio output stream with an open input stream can crash the ALSA backend.

## 6. Known limitations and upgrade paths

- Monocular distance is a proxy from bounding-box height. It is coarse and class-dependent. The clean upgrade is a real depth source, such as a VL53L5CX time-of-flight sensor over I2C or a depth model on the AI Kit. announcer.estimate_distance_m is the single call site to replace.
- CPU detection is a few frames per second. Fine for walking, marginal for fast motion. The Hailo-8L backend stub is the upgrade.
- dlib face recognition is heavy on CPU. The face paths already downscale and skip frames. For many enrolled faces, consider MediaPipe or an on-NPU embedder.
- Power and thermals are not managed here. A real build wants a low-power idle and a thermal check, since the Pi 5 can throttle under sustained inference.

## 7. Testing

The pure logic has a pytest suite that runs without a camera or a network: announcement phrasing and throttling, config merging, the spatial-audio tone generator, the headless startup branch, the thread-safe speaker, and the shared image encoder. Run it with `.venv/bin/python -m pytest`. The capabilities that need hardware or the cloud are exercised by running the demos.

## 8. Extending

Add a capability by writing a demo that composes Camera, Speaker, AudioCues, and optionally Detector or Announcer, then register it. For the button controller, add a row to MODES in main.py. For the voice app, add a cmd_ method and the command word to the recogniser's command set. The shared services are the contract, so nothing else needs to change.
