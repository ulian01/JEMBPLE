# Using Sightline

This is a guide to operating Sightline day to day. It assumes the device is already set up. If you still need to install it, see README.md.

## What you wear and what you hear

Sightline is a small camera and computer on an arm strap, with the camera facing forward. You hear it through a speaker or headset. Bone-conduction headphones are best, because they sit in front of your ears and leave your ears open, so you can still hear traffic, voices, and the room around you.

The device speaks to you for content, such as reading a sign or naming a person. It also uses short beeps for two things that are quicker to feel than to say: direction and distance. A beep that is louder in your left ear means the thing is on your left. A beep that is higher and faster means the thing is closer.

## Talking to it

Sightline listens for the wake word "sight". To give a command, say "sight" and then the command, for example:

```
sight describe
sight text
sight who
```

As soon as it hears "sight" you get a short two-note chime. That chime is your confirmation that it is listening, and it also stops whatever the device was saying. So if it is in the middle of a long sentence and you want something else, just say "sight" and carry on with your command.

If you are setting the device up for someone else, or testing it yourself, the same commands are on screen as buttons and on the keyboard. More on that near the end.

## The commands

Most commands have a few natural alternatives, so "read" works as well as "text", "again" works as well as "repeat", and so on. The alternatives are listed in brackets.

Reading and the world around you:

- text (read): reads any text in view out loud. If there is a lot of text it reads the first part and then waits. Say "sight next" for the next part.
- next (more, continue): continues reading the next part of a long text.
- spell: spells out the last text letter by letter. Useful for a code, a reference number, or an unusual word.
- money (cash, note): tells you what banknotes and coins are in view and the total.
- label (ingredients, expiry, dosage): reads a product label and focuses on the useful parts, such as the product name, allergens, the best-before date, and the dosage on medicine.
- translate (english): reads any text in view and translates it into English.
- barcode (scan): scans a barcode or QR code. For a shop product it looks up the name. For a QR code it reads out what the code contains.

Scene and people:

- describe (scene): gives you a short spoken description of the whole scene in front of you, leading with what matters most.
- face (identify): tells you who the nearest person is, if you have enrolled them. If it does not know them, it says so.
- who (everyone): lists the people it can see, and how many it does not recognise.
- remember (save): enrols the person in front of you so it can name them later. It asks for their name, you say the name after the tone, and it saves them straight away.
- expression (mood, looking): describes the nearest person's expression and whether they seem to be looking toward you.

Comfort and control:

- repeat (again): says the last thing again.
- faster, slower: change the speaking speed.
- louder, quieter (softer): change the volume.
- stop (quiet, cancel): stops talking right away. Saying "sight" on its own does the same thing.

Status:

- help: lists the commands out loud.
- battery: tells you the battery level, if the device can read it.
- time: tells you the current time.
- date: tells you the day and date.

A toggle:

- distance (beeps): turns the proximity beeps on or off. They start off. When you turn them on, you hear a low beep for nearby obstacles that gets faster and higher as something gets closer, panned to the side it is on. Turn them on when you are moving around, off when you are sitting still.

While the device is on, it quietly watches for objects in the background the whole time. The distance beeps are the part you switch on and off.

## Enrolling a face

There are two ways to teach Sightline a face.

By voice, in the moment. Point the camera at the person and say "sight remember". The device says "Who is this? Say their name after the tone." After the tone, say the name, for example "Mum" or "Daniel". It saves the face and says the name back to confirm. From then on, "sight face" and "sight who" will recognise them. For a clean result, have one person in front of the camera, reasonably close, in good light.

Ahead of time, with help. A sighted helper can enrol someone from a terminal:

```
python3 demos/enroll_face.py "Mum"
```

The person faces the camera, and it saves them once it sees a single clear face.

## Reading longer text

When you say "sight text" and there is a lot to read, such as a letter or a menu, the device reads it in parts so it does not become one long stream. After each part it tells you to say "next" to continue. Say "sight next" for the following part, and keep going until it says there is no more text. If you want a tricky word spelled out, say "sight spell" and it spells the last thing it read.

## Getting good results

- Point the camera at what you care about and hold steady for a second before the command.
- Light matters. Reading and face recognition both work much better in good light.
- For reading, try to fill the view with the text and hold the item square to the camera rather than at a steep angle.
- For money and labels, hold the item still and close enough to fill the frame.

## When you are not using voice

Voice is the main way in, but everything has a fallback, which is also handy for a sighted helper or for testing.

In the voice app window there are on-screen buttons and matching keyboard keys: TEXT (t), DESCRIBE (d), FACE (f), DISTANCE (b), HELP (h), and QUIT (q). These do the same thing as the spoken commands.

There is also a simpler two-button controller, main.py, for a build that has no voice model installed. It runs one capability at a time. One button, MODE, steps through the capabilities and says each one as you reach it: object detection, face recognition, obstacle alerts, text reader, then scene describer. The other button, ACTION, takes a single reading in the two on-demand modes (text reader and scene describer). On a keyboard these are m for mode, a for action, and q to quit. On the strap, MODE is the button on GPIO 17 and ACTION is the button on GPIO 27.

## If something is not working

- It does not answer when you say "sight". Check the speaker or headset is on and the microphone is connected. Try the buttons or keys to confirm the rest is working. If voice was never installed, the device runs in button mode only.
- It says a service is unavailable. That capability needs something that is not set up on this device. Scene description and the most accurate reading need an internet connection and an API key. Face commands need the face library installed.
- It does not recognise someone you enrolled. Try again in better light and a bit closer. Enrol them once more if needed, since a clearer enrolment photo helps.
- On a laptop, the preview window is black. Another program may be holding the webcam, or the wrong camera is selected. Run `python tools/camera_check.py` to find a working one.
