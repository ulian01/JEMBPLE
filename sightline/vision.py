"""On-demand visual question answering via Claude vision.

Powers the money / label / translate / expression commands. Each is a single
non-streaming call with a task-specific prompt, tuned to return short, spoken,
markdown-free answers. Cheap on a small model like claude-haiku-4-5.
"""
from __future__ import annotations

from .imaging import encode_jpeg

try:
    import anthropic
except Exception:
    anthropic = None

_MONEY = (
    "You help a blind person handle cash. Identify the banknotes and coins visible "
    "and state the total and currency if you can tell. One or two short sentences, "
    "spoken style, no markdown. If you can't see money clearly, say so."
)
_LABEL = (
    "You read product labels for a blind shopper. Read out the key information: the "
    "product name, any allergens, the expiry or best-before date, and dosage or "
    "directions if it's medication. Be concise and spoken, no markdown. If the text "
    "is unreadable, say so."
)
_TRANSLATE = (
    "Read any text in the image and translate it into English. Output only the "
    "English translation in plain spoken style — no preamble, no markdown. If there "
    "is no text, say there is no text to translate."
)
_EXPRESSION = (
    "Look at the person facing the camera. In one short spoken sentence, describe "
    "their facial expression and apparent mood, and whether they appear to be "
    "looking toward the camera. If no face is visible, say so."
)


class VisionAssistant:
    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 320,
                 max_edge: int = 1280):
        if anthropic is None:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.max_edge = max_edge

    def query(self, frame_bgr, system: str, user: str = "Answer briefly.") -> str:
        b64 = encode_jpeg(frame_bgr, self.max_edge)
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": user},
                ],
            }],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    def money(self, frame):       return self.query(frame, _MONEY, "How much money is shown?")
    def label(self, frame):       return self.query(frame, _LABEL, "Read this label.")
    def translate(self, frame):   return self.query(frame, _TRANSLATE, "Translate the text to English.")
    def expression(self, frame):  return self.query(frame, _EXPRESSION, "Describe their expression.")
