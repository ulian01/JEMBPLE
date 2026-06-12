# Sightline

Sightline is a wearable assistive-vision system for blind and low-vision users. A Raspberry Pi 5 with a camera and a battery pack, worn on an arm strap, turns what the camera sees into speech and spatial audio. You hear it through a speaker or, ideally, a bone-conduction headset that leaves your ears open to the world around you.

This repository contains five vision capabilities, a shared library that all of them are built from, and two ways to drive the device:

- A voice assistant (app.py) that listens for a wake word and runs continuously.
- A two-button controller (main.py) that cycles through one capability at a time.

If you just want to use the device, read USE.md. For the technical design, read ARCHITECTURE.md.

## The five capabilities

| Capability | What you get | Where it runs |
| --- | --- | --- |
| Object detection | Names of nearby objects and roughly where they are, such as "a person, to your left, close". Configurable vocabulary, from 80 common classes up to about 600, or your own named objects | On device |
| Face recognition | Names of people you have enrolled, such as "I see Mum, ahead" | On device |
| Text reader (OCR) | Signs, mail, labels, and menus read aloud | Claude vision, EasyOCR, or Tesseract |
| Scene description | A short spoken summary of the whole scene | Off device (Claude) |
| Obstacle alerts | Parking-sensor beeps that speed up as something gets closer | On device |

Direction is carried by stereo panning, so an object on your left is louder in your left ear. Proximity is carried by pitch and beep rate, so closer means higher and faster. Speech is saved for content. The fast, urgent information stays in a channel you can react to instantly.

## The voice assistant

app.py is the everyday mode. It always listens for the wake word "sight" and runs object detection in the background. You say "sight" followed by a command, for example "sight describe" or "sight text". Saying "sight" on its own also interrupts whatever the device is currently saying, so you are never stuck waiting for a long sentence to finish.

The full command list is in USE.md. Speech recognition is offline (Vosk) with a small grammar limited to the command words, which keeps it fast and accurate on the Pi. Every capability is optional and degrades gracefully. No API key disables scene description and the cloud reader. No voice model falls back to on-screen buttons and keyboard keys. No face library disables the face commands.

## Hardware

- Raspberry Pi 5 (4 GB)
- Raspberry Pi Camera Module 3 (or v2) on the CSI ribbon
- USB power bank (a 10000 mAh bank gives roughly a day of light use)
- A speaker over USB or Bluetooth. The Pi 5 has no 3.5 mm jack, so analog speakers need a USB DAC or an I2S audio HAT. Bone conduction is recommended.
- Optional: two momentary push-buttons wired to GPIO 17 and GPIO 27
- Optional: Raspberry Pi AI Kit (Hailo-8L) for faster detection
- An arm strap to hold it all, with the camera facing forward

## Setup on the Raspberry Pi

System packages:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv tesseract-ocr cmake \
                    libcamera-apps espeak-ng
```

Python environment:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Object detection: the Pi profile uses YOLO via ultralytics with the nano Open Images model (about 600 object classes), which auto-downloads on first run (about 7 MB). Install it with `pip install ultralytics`. For a lighter, no-torch footprint you can switch to the TFLite backend (80 COCO classes) in config.yaml; see models/README.md for that model.

Scene description and the most accurate text reader use Claude, so set your key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Offline voice commands: run tools/install_voice.sh once to fetch Vosk and a small model, then point voice.model at it in config.yaml. Until that is set, the voice app falls back to buttons and keys. Better speech output is optional: run tools/install_piper.sh and set speech.engine to piper, otherwise eSpeak-NG is used.

Everything is driven by config.yaml: resolution, audio device, model paths, thresholds, the scene model, and the GPIO pins. It overlays the defaults in sightline/config.py, so you only need to set the values you want to change.

## Run on the Pi

```bash
python3 app.py     # voice assistant, the everyday mode
python3 main.py    # two-button controller (m = next mode, a = capture, q = quit)
```

You can also run a single capability on its own:

```bash
python3 demos/01_object_detector.py
python3 demos/05_obstacle_alert.py
python3 demos/03_text_reader.py        # press Enter to read
python3 demos/04_scene_describer.py    # press Enter to describe
python3 demos/enroll_face.py "Mum"     # enrol a face, then use the face commands
```

To start on boot, install systemd/sightline.service. When it runs without a terminal it starts in headless mode automatically and is driven by the GPIO buttons.

## Run on a laptop

The whole suite runs on a normal laptop with the built-in webcam, no Pi needed. The laptop profile swaps in the webcam, a visible preview window so you can see the overlays, and the YOLO detector that downloads its own weights.

```bash
./setup_laptop.sh
source .venv/bin/activate
export SIGHTLINE_CONFIG=config.laptop.yaml
export ANTHROPIC_API_KEY=sk-ant-...    # only for the scene and cloud reader

python3 app.py
python3 demos/01_object_detector.py
```

Useful knobs in config.laptop.yaml:

- camera.source: 0 for the default webcam, or a path to a video or image to test against a fixed clip.
- display.preview: true shows the annotated window. Press q to quit.
- object_detection: the laptop profile uses yolov8s-oiv7.pt, a YOLO model with about 600 Open Images classes, so it names far more objects than the 80-class COCO default. Lower imgsz (for example 416) for speed, set threaded to keep detection off the camera loop, or list your own classes under open_vocab to detect anything by name.
- scene.model and ocr.model: drop to claude-haiku-4-5 for faster, cheaper local testing.
- scene.style: succinct gives terse fragments, full gives short sentences.

Face recognition is optional on a laptop because dlib compiles from source. setup_laptop.sh prints the extra step.

## Tests

The core logic has a pytest suite that needs no camera and no network:

```bash
.venv/bin/python -m pytest
```

It covers the announcement phrasing and throttling, config merging, the spatial-audio tone generator, the headless startup path, the thread-safe speaker, the shared image encoder, the focused describe sub-command, and the Bluetooth manager.

## Layout

```
app.py             voice assistant (wake word, always on)
main.py            two-button mode controller
sightline/         shared library
  camera.py        Picamera2 with an OpenCV webcam fallback, BGR frames
  speech.py        threaded, thread-safe text to speech with a priority queue
  audio_cues.py    stereo panned and pitched earcons for direction and distance
  announcer.py     throttling, box-to-phrase, and the shared obstacle class list
  detector.py      object detection (TFLite, YOLO, Hailo stub)
  faces.py         enrol and recognise faces
  ocr.py           text reading (Claude, EasyOCR, Tesseract)
  scene.py         scene description via Claude vision
  vision.py        money, label, translate, and expression via Claude vision
  imaging.py       shared JPEG encode and downscale for the vision calls
  listen.py        offline wake-word and command recognition (Vosk)
  barcode.py       barcode and QR reading with product lookup
  sysinfo.py       battery status
  viz.py           optional preview window and on-screen buttons
  config.py        defaults plus config.yaml overlay
demos/             the five capabilities and face enrolment, runnable on their own
tests/             pytest suite for the pure logic
tools/             camera check, OCR check, Piper and Vosk installers
models/            TFLite model and COCO labels (see models/README.md)
systemd/           boot service
config.yaml        Raspberry Pi profile
config.laptop.yaml laptop and webcam profile
```
