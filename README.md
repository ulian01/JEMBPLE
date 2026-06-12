# Sightline

A wearable assistive-vision suite for blind and low-vision users. A Raspberry Pi
5 + Pi Camera + battery, worn on an arm strap, turns what the camera sees into
**speech and spatial audio** through a speaker or bone-conduction headset.

This repo is a working demonstration of five complementary capabilities, plus
the shared plumbing (camera, speech, spatial audio, throttling) and an on-body
mode controller that ties them together with two buttons.

---

## Production app (`app.py`) — voice-controlled

One always-on assistant combining everything, driven by a **wake word + command**.
Saying **"SIGHT"** also barges in — it stops whatever it's currently saying.

| Category | Commands |
|----------|----------|
| **Reading** | `text` (OCR, paginated — `next` for more), `spell`, `money`, `label` (allergens/expiry/dosage), `translate` (→ English), `barcode` |
| **Scene & people** | `describe`, `face` (who is this), `who` (everyone in view), `remember` (enrol a face by voice: *"SIGHT remember"* → say the name), `expression` (mood / looking at me) |
| **Control** | `repeat` (replay last), `faster`, `slower`, `louder`, `quieter`, `stop` |
| **Status** | `help`, `battery`, `time`, `date` |
| **Toggle** | `distance` (low proximity beeps; off by default) |

Most commands have natural synonyms (`read`→text, `again`→repeat, `cash`→money,
`scan`→barcode, `who's here`→who, …). Background: object detection + optional
distance beeps run continuously regardless.

Continuously in the background it detects objects and emits **parking-sensor
beeps** — faster and higher-pitched as an obstacle gets closer, panned to where
it is. A window shows the live feed with detections, status, and the last
response, plus clickable **TEXT / DESCRIBE / FACE** buttons (keys `t`/`d`/`f`) as
a no-voice fallback.

Speech-to-command is **offline** (Vosk, with a grammar limited to the command
phrases — fast and accurate on a CPU). Run once: `tools/install_voice.sh`.

```bash
export SIGHTLINE_CONFIG=config.laptop.yaml
export ANTHROPIC_API_KEY=sk-ant-...        # for describe + Claude OCR
bash tools/install_voice.sh                # one-time: Vosk + model
python app.py                              # then say: "SIGHT describe"
```

Every capability is optional and degrades gracefully — no API key disables
describe (buttons say so), no Vosk model falls back to the buttons/keys, no
`face_recognition` disables the face command. Config lives under `voice:` and
`app:` in `config.yaml`.

The individual demos below remain as focused, single-feature references.

## The five capabilities

| # | Demo | What it does | Where it runs |
|---|------|--------------|---------------|
| 1 | `demos/01_object_detector.py` | Names objects around you and roughly where they are — *"a person, to your left, close"* | On-device (TFLite) |
| 2 | `demos/02_face_recognizer.py` | Recognises people you've enrolled — *"I see Mum, ahead"* | On-device (dlib) |
| 3 | `demos/03_text_reader.py` | Reads signs, mail, labels, menus aloud (OCR) | Claude vision / EasyOCR / Tesseract |
| 4 | `demos/04_scene_describer.py` | Rich natural description of the whole scene via a vision-language model | **Off-device** (Claude API) |
| 5 | `demos/05_obstacle_alert.py` | Parking-sensor-style proximity warnings as things get close | On-device (TFLite) |

`main.py` is the controller: **MODE** cycles capabilities (spoken aloud),
**ACTION** triggers a capture in the on-demand modes (text / scene). On a laptop
those are the `m` and `a` keys; on the strap they're two GPIO push-buttons.

---

## Why these design choices

**Audio-first, eyes-free.** There is no screen. Everything is speech plus
non-speech *earcons*. Direction is conveyed by **stereo panning** (an object on
your left is louder in your left ear) and proximity by **pitch + repetition
rate** (closer = higher and faster) — both are perceived almost instantly,
where a spoken sentence is slow and serial. Speech is reserved for content;
beeps carry direction and urgency.

**Use bone-conduction headphones, not earbuds.** A blind user relies on ambient
hearing for safety. The output device should *augment* hearing, not block it —
bone conduction leaves the ear canal open. (Configurable; any ALSA device works.)

**Don't flood the user.** The `Announcer` suppresses repeats of the same label
for a few seconds and only speaks the single most-confident new object per
frame, so the device informs rather than babbles.

**On-device by default, off-device when it pays off.** Detection, recognition
and OCR run locally — low latency, works offline, private. The one capability
that genuinely benefits from the cloud is *holistic scene understanding*: a
vision-language model describes context and layout in a way no on-device 6 MB
model can. That's an on-demand button press (needs network + API key), not a
continuous loop, so latency and cost stay bounded.

**Safety has priority.** Obstacle warnings use the fast audio channel and can
interrupt queued speech (`Speaker.PRIORITY_HIGH`).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full hardware/software design,
data flow, and trade-offs.

---

## Hardware

- Raspberry Pi 5 (4 GB)
- Raspberry Pi Camera Module 3 (or v2) via the CSI ribbon
- USB power bank (a 10000 mAh bank ≈ a full day of light use)
- Speaker: **USB or Bluetooth** — note the Pi 5 has **no 3.5 mm jack**, so analog
  speakers need a USB DAC or an I²S audio HAT. Bone-conduction recommended.
- Optional: two momentary push-buttons (MODE / ACTION) to GPIO 17 / 27
- Optional: Raspberry Pi AI Kit (Hailo-8L) for 30+ FPS detection
- Arm strap / armband to hold it all, camera facing forward

---

## Setup

```bash
# System packages (Raspberry Pi OS)
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv tesseract-ocr cmake \
                    libcamera-apps espeak-ng

# Python deps
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt

# Object-detection model (see models/README.md)
#   downloads the TFLite SSD-MobileNet COCO model into models/

# Off-device scene describer
export ANTHROPIC_API_KEY=sk-ant-...

# Better-sounding speech (optional): install Piper and point speech.piper_model
#   at a voice .onnx in config.yaml. Otherwise eSpeak-NG is used.
```

Everything is driven by `config.yaml` (resolution, audio device, model paths,
thresholds, the scene-describer model, GPIO pins). It overlays
`sightline/config.py` defaults, so it's safe to trim.

---

## Run

```bash
# Full controller (two-button, eyes-free)
python3 main.py            # m = next mode, a = action, q = quit

# Or run a single capability directly
python3 demos/01_object_detector.py
python3 demos/05_obstacle_alert.py
python3 demos/03_text_reader.py        # press Enter to read
python3 demos/04_scene_describer.py    # press Enter to describe
python3 demos/enroll_face.py "Mum"     # enrol a face, then run demo 2
```

Autostart on boot via `systemd/sightline.service`.

## Run it locally on your LMDE laptop

The whole suite runs on a normal laptop using the built-in **webcam** — no Pi
needed for development. The local profile swaps in the webcam, a visible
**preview window** (you can see the overlays), and the **YOLO** detector that
auto-downloads its own weights (no TFLite/model wrangling).

```bash
./setup_laptop.sh                      # venv + deps (webcam, YOLO, OCR, TTS, scene)
source .venv/bin/activate
export SIGHTLINE_CONFIG=config.laptop.yaml
export ANTHROPIC_API_KEY=sk-ant-...    # only for demo 4 (scene describer)

python3 demos/01_object_detector.py    # webcam + live preview, spoken + panned audio
python3 demos/05_obstacle_alert.py
python3 demos/03_text_reader.py        # press Enter to read text in view
python3 demos/04_scene_describer.py    # press Enter to describe the scene
python3 main.py                        # full controller: m = mode, a = action, q = quit
```

Knobs in [`config.laptop.yaml`](config.laptop.yaml):

- `camera.source` — `0` for the default webcam, `1`/`2` for others, or a **path
  to a video or image** to test against a fixed clip (videos loop).
- `display.preview` — `true` shows the annotated window; press `q` to quit.
- `object_detection.backend: ultralytics` — YOLO; first run downloads `yolov8n.pt`.
- `scene.model` — drop to `claude-haiku-4-5` for faster/cheaper local testing.
- `ocr.backend` — `auto` uses **Claude vision** when `ANTHROPIC_API_KEY` is set
  (far more accurate on real-world signs/labels than Tesseract), then EasyOCR,
  then Tesseract. Verify on a still: `python tools/ocr_test.py photo.jpg`.
- `scene.style` — `succinct` (default) speaks terse fragments ("Person ahead,
  close. Door right.") — quick to hear and cheap; `full` gives sentences.
- **DESCRIBE button** — the text-reader window has a clickable **DESCRIBE**
  button (key `d`) that speaks a succinct scene description; the scene-describer
  window does the same on SPACE.
- **Cheap + accurate** — pair `claude-haiku-4-5` with `style: succinct` (output
  capped ~160 tokens). Haiku vision is plenty accurate for OCR and terse scenes
  at a fraction of Opus's cost.
- **Better voice** — run `tools/install_piper.sh` for natural offline TTS
  (Piper), then set `speech.engine: piper`. (Whisper is speech-to-*text*, so it
  can't voice output; eSpeak-NG is the zero-setup fallback.)

Face recognition (demo 2) is optional locally because dlib compiles from source;
`setup_laptop.sh` prints the one extra step. Everything degrades gracefully: no
TTS engine ⇒ speech prints to the console; headless ⇒ the preview disables itself.

---

## Layout

```
sightline/        shared library (import these from any demo)
  camera.py        Picamera2 with OpenCV fallback → BGR frames
  speech.py        threaded TTS (Piper → eSpeak fallback), priority queue
  audio_cues.py    stereo panned / pitched earcons for direction & proximity
  announcer.py     throttling + box→phrase ("a chair, ahead, close")
  detector.py      TFLite object detection (Hailo backend stub)
  config.py        defaults + config.yaml overlay
demos/            the five capabilities + face enrolment
models/          TFLite model + COCO labels (see models/README.md)
systemd/         boot service
main.py          two-button mode controller
config.yaml      all tunables
```
