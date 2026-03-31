🕶️ JEMBPLE – AI Assistive Smart Glasses & Gloves

“We Are Leading the Blind”

An AI-powered wearable system designed to help blind and visually impaired individuals navigate the world independently using real-time audio and haptic feedback.

📌 Project Overview

JEMBPLE is an assistive technology system built around smart glasses and wearable accessories (gloves / feedback modules) that enhance environmental awareness for blind and low-vision users.

The system combines:

👁️ Computer Vision
📡 LiDAR sensing
🧠 AI-based object recognition
🔊 Audio + vibration feedback

to transform visual information into real-time, understandable feedback.

The goal is simple:

Increase independence, safety, and confidence in everyday life.

🌍 Why This Matters

According to the World Health Organization, over 2.2 billion people experience visual impairment globally .

Existing tools like:

White canes
Guide dogs

are helpful — but limited.

JEMBPLE expands these capabilities using AI to:

Understand environments
Identify objects
Provide contextual guidance
🎯 Core Features
🚌 Smart Navigation
Detects buses and reads route numbers
Identifies crosswalks and safe crossing moments
🛒 Daily Independence
Reads product labels and prices
Scans menus (even without braille)
🚧 Obstacle Detection
Detects static & moving obstacles
Alerts users before collisions
🍳 Cooking Assistance
Recognizes food states (raw → cooked → burnt)
Gives real-time cooking feedback
🧭 Environmental Awareness
Reads signs (bathrooms, street names, house numbers)
Describes surroundings in real time
⚙️ How It Works (System Flow)
Example: Reading a Price Label
User taps glasses or says “Read this”
Camera captures image
OCR extracts text
AI processes relevant info
Text-to-speech outputs result
Example: Bus Detection
Continuous scanning
Object detection finds bus
OCR reads number
Audio: “Bus 42 approaching”
Example: Cooking Assistance
Camera observes food
AI classifies state
Audio: “The onions are golden brown”
🧠 Technical Architecture

The system is divided into 3 main modules:

1. Sensing Module (Glasses)
📷 AI Camera
📡 LiDAR sensor
Captures real-time environmental data
2. Processing Module (External)
Microcontroller / compute unit
Handles:
Object detection
OCR
AI inference
Can use hybrid processing:
Local → fast responses
Cloud → complex analysis
3. Feedback Module
🎧 Bone conduction headphones
📳 Vibration feedback (gloves / motors)

➡️ This separation reduces weight on the glasses and improves comfort

🔌 Hardware Overview
Component	Function
LiDAR Sensor	Distance & obstacle detection
AI Camera	Object & text recognition
Microcontroller	Data processing
Powerbank (27,000 mAh)	Power supply
Bone Conduction Headphones	Audio feedback
Vibration Motor / Gloves	Haptic feedback
⚡ Performance
⏱️ Latency: <150ms (local processing)
🔋 Battery: 8–10 hours usage
📏 LiDAR accuracy: ~3 cm error margin
🧪 Testing

The system was tested across multiple scenarios:

Key Test Cases
ID	Test	Priority
TC-01	Static obstacle detection	High
TC-02	Moving obstacle detection	High
TC-03	Object recognition	High
TC-04	Low-light performance	Medium
TC-05	Battery performance	Medium
TC-06	Connectivity	Medium
TC-07	Failure handling	High
TC-08	Text recognition	Medium
TC-09	System startup	High
TC-10	Usability	High
Example Result
Obstacles detected reliably within safe distance
Audio warnings delivered clearly and on time
⚠️ Challenges & Limitations
Low-light affects camera performance
Reflective surfaces impact LiDAR
Cloud processing introduces latency
Battery life vs performance trade-offs
Risk of user overstimulation (too much feedback)
👥 Team
Name	Role
Bart	Consultant / Mediator
Ebenezer	Planner
Julian	Implementer / Secretary
Mae	Creative
Penelope	Chairman / Quality Lead
Larry	Specialist / Finisher
Esmee	Manager / Team Leader
🤝 Code of Conduct
Be responsible, respectful, and communicative
Ask for help when needed
Solve problems together as a team
🔧 Development & Git Workflow
Structured branching (main / feature / bugfix)
Clean commit history
Pull requests & code reviews
Organized repository structure
🚀 Future Improvements
Better low-light vision models
Faster on-device AI processing
Improved battery efficiency
Smarter feedback filtering (reduce overload)
Enhanced wearable integration (gloves + glasses synergy)
💡 Vision

JEMBPLE is more than a project — it’s a step toward:

A world where blindness does not limit independence.

If you want, I can also:

Add badges (GitHub style)
Create a cool project logo/banner
Add installation/setup section (code-based)
Or make it match your anti-procrastination project aesthetic
