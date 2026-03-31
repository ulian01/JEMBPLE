# 🕶️ JEMBPLE: AI Assistive Smart Glasses & Gloves
> **"We Are Leading the Blind"**

![Status: Active](https://img.shields.io/badge/Status-Active-success?style=flat-square)
![Hardware: Integrated](https://img.shields.io/badge/Hardware-Custom_Wearable-blue?style=flat-square)
![AI: Computer Vision](https://img.shields.io/badge/AI-Computer_Vision-orange?style=flat-square)
![Sensors: LiDAR](https://img.shields.io/badge/Sensors-LiDAR-lightgrey?style=flat-square)

An AI-powered wearable system designed to help blind and visually impaired individuals navigate the world independently using real-time audio and haptic feedback.

## 🌍 Why This Matters
According to the World Health Organization, over **2.2 billion people** experience visual impairment globally. While existing tools like white canes and guide dogs are invaluable, they have physical limitations. JEMBPLE expands these capabilities using modern AI to understand environments, identify objects, and provide contextual guidance—increasing independence, safety, and confidence in everyday life.

---

## 🎯 Core Features

* **🚌 Smart Navigation:** Detects buses, reads route numbers, and identifies safe moments to use crosswalks.
* **🛒 Daily Independence:** Reads product labels, prices, and scans menus (removing the reliance on braille-only options).
* **🚧 Obstacle Detection:** Identifies both static and moving obstacles, alerting users *before* a collision occurs.
* **🍳 Cooking Assistance:** Recognizes food states (e.g., raw → cooked → burnt) to provide real-time culinary feedback.
* **🧭 Environmental Awareness:** Reads environmental text like bathroom signs, street names, and house numbers, describing the surroundings in real time.

---

## 🧠 Technical Architecture

JEMBPLE is divided into three distinct modules to distribute weight, optimize compute power, and maximize user comfort.

### 1. Sensing Module (Glasses)
* **📷 AI Camera:** Captures high-resolution, real-time visual data.
* **📡 LiDAR Sensor:** Provides precise depth mapping and distance measurement.

### 2. Processing Module (External/Wearable Compute Unit)
* **Microcontroller:** Handles routing, object detection, OCR (Optical Character Recognition), and AI inference.
* **Hybrid Processing:** Prioritizes local processing for fast (<150ms) emergency responses, falling back to cloud processing for complex scene analysis.

### 3. Feedback Module (Output)
* **🎧 Audio:** Bone conduction headphones deliver clear text-to-speech without blocking ambient environmental sounds.
* **📳 Haptics:** Vibration feedback (via gloves or localized motors) provides silent, intuitive directional cues.

---

## ⚙️ System Flow in Action

**Scenario: Reading a Price Label**
> 1️⃣ User taps glasses or uses voice wake-word ("Read this").
> 2️⃣ Camera captures the image.
> 3️⃣ OCR extracts the text and AI processes the relevant info.
> 4️⃣ Text-to-speech outputs: *"Apple Juice, $3.99."*

**Scenario: Bus Detection**
> 1️⃣ System continuously scans the environment.
> 2️⃣ Object detection identifies an approaching bus.
> 3️⃣ OCR reads the LED route number.
> 4️⃣ Audio alerts: *"Bus 42 approaching."*

---

## 🔌 Hardware Specifications

| Component | Function | Notes |
| :--- | :--- | :--- |
| **LiDAR Sensor** | Distance & obstacle detection | ~3 cm error margin |
| **AI Camera** | Object & text recognition | Optimized for low latency |
| **Microcontroller** | Core data processing | Handles local AI/OCR pipelines |
| **Powerbank** | Power supply | 27,000 mAh (approx. 8–10 hours usage) |
| **Headphones** | Audio feedback | Bone conduction for situational awareness |
| **Vibration Motors** | Haptic feedback | Integrated into gloves/wearables |

---

## 🧪 Testing & Performance

The system is rigorously tested across multiple scenarios to ensure safety and reliability.

* **Latency:** < 150ms (for local processing)
* **Battery Life:** 8–10 hours of active usage

### Key Test Cases
| ID | Test Scenario | Priority | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `TC-01` | Static obstacle detection | **High** | Detected reliably within a safe stopping distance. |
| `TC-02` | Moving obstacle detection | **High** | Real-time tracking with predictive warnings. |
| `TC-03` | Object recognition | **High** | Fast identification of everyday items. |
| `TC-04` | Low-light performance | Medium | Maintains basic LiDAR functionality if vision drops. |
| `TC-07` | Failure handling | **High** | Fails safely; alerts user if sensors are blocked. |

> ⚠️ **Current Limitations:** Low-light environments currently affect camera performance. Highly reflective surfaces can occasionally scatter LiDAR readings. We are actively working on filtering algorithms to prevent "user overstimulation" (too much feedback at once).

---

## 🚀 Future Roadmap
- [ ] Implement better low-light vision models.
- [ ] Optimize on-device AI for even faster processing without the cloud.
- [ ] Improve battery efficiency and reduce component weight.
- [ ] Develop smarter feedback filtering to prioritize critical alerts (reducing audio/haptic overload).
- [ ] Enhance synergy between the glasses and the haptic gloves.

---

## 👥 The Team

| Name | Role |
| :--- | :--- |
| **Penelope** | Chairman / Quality Lead |
| **Esmee** | Manager / Team Leader |
| **Bart** | Consultant / Mediator |
| **Ebenezer** | Planner |
| **Julian** | Implementer / Secretary |
| **Mae** | Creative |
| **Larry** | Specialist / Finisher |

---

## 🤝 Contributing & Workflow

**Code of Conduct:** Be responsible, respectful, and communicative. Ask for help when needed, and solve problems together as a team.

**Development Workflow:**
1. Structured branching (`main` / `feature/your-feature` / `bugfix/issue`).
2. Maintain a clean, descriptive commit history.
3. All merges to `main` require Pull Requests and code reviews.

---

## 💻 Installation & Setup (Placeholder)
*(Add your specific hardware flashing instructions or software dependencies here)*

```bash
# Example: Clone the repository
git clone [https://github.com/your-org/jembple.git](https://github.com/your-org/jembple.git)
cd jembple

# Install dependencies
pip install -r requirements.txt

# Run the local testing environment
python main.py --mode debug
```
