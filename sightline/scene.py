"""Scene description via a vision model, with a cheap, terse default.

Two styles:

* **succinct** (default) — clipped, telegraphic fragments ("Person ahead, close.
  Door right. Steps down, left."). Faster to hear, fewer output tokens, cheaper.
  Pairs well with a cheap model like ``claude-haiku-4-5``.
* **full** — 2-4 natural spoken sentences for richer context.

The reply is streamed and spoken fragment-by-fragment to cut perceived latency.
"""
from __future__ import annotations

from .imaging import encode_jpeg

try:
    import anthropic
except Exception:
    anthropic = None

_SUCCINCT_SYSTEM = (
    "You are the eyes of a blind person, giving rapid spoken guidance through an "
    "earpiece. Describe the scene in ultra-terse fragments — no full sentences, no "
    "articles, no filler words. Each fragment is at most 3 words and ends with a "
    "period. Put the most important and nearest things first; prioritise obstacles, "
    "people, exits, hazards, and layout, each with a direction (left / ahead / "
    "right). Example: 'Person ahead, close. Door right. Steps down, left. Table "
    "left.' Output only the fragments — nothing else."
)

_FULL_SYSTEM = (
    "You are the eyes of a blind person wearing a chest-mounted camera. Describe "
    "the scene concisely and usefully for someone who cannot see it. Lead with the "
    "most important thing. Mention layout and rough direction (left / ahead / "
    "right) and anything relevant to safety or navigation (steps, doorways, "
    "obstacles, traffic). Use plain spoken language, 2-4 short sentences. Respond "
    "with only the description — no preamble, no 'I see', no markdown, no lists."
)

_SUBJECT_SYSTEM = (
    "You are the eyes of a blind person. They have asked about one specific thing "
    "in view. Describe just that thing in clear, spoken language: what it is, its "
    "colour and condition, any text, labels, or markings on it, and anything "
    "practically useful such as which way it faces, how to open or use it, or "
    "whether it is plugged in or switched on. Two to four short sentences. If you "
    "cannot find it, say so in one short sentence. No preamble, no markdown."
)


class SceneDescriber:
    def __init__(self, scene_cfg: dict):
        if anthropic is None:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")
        self.model = scene_cfg.get("model", "claude-haiku-4-5")
        self.style = scene_cfg.get("style", "succinct")
        self.max_edge = int(scene_cfg.get("max_image_edge", 1024))
        # succinct output is tiny; cap tokens low to keep it cheap and fast
        self.max_tokens = int(scene_cfg.get("max_tokens", 400))
        if self.style == "succinct":
            self.max_tokens = min(self.max_tokens, 160)
        self.client = anthropic.Anthropic()

    def _system(self) -> str:
        return _SUCCINCT_SYSTEM if self.style == "succinct" else _FULL_SYSTEM

    def describe(self, frame_bgr, speaker=None, on_update=None, subject=None) -> str:
        """Stream the description text to the GUI, then speak it once.

        With ``subject`` set (for example "usb cable"), focus on that one thing
        and describe it in more detail instead of summarising the whole scene.

        We stream for the *visual* update (``on_update(full_text_so_far)``) but
        speak the whole result as a single utterance — speaking per-sentence
        would spawn a fresh TTS process at every full stop, which is the real
        source of long pauses on periods. Returns the full text.
        """
        subject = (subject or "").strip()
        if subject:
            system = _SUBJECT_SYSTEM
            user_text = (
                f"Focus on the {subject} in the image and describe it in detail. "
                f"If there is no {subject} in view, say so in one short sentence."
            )
            max_tokens = max(self.max_tokens, 300)   # room for a detailed answer
        else:
            system = self._system()
            user_text = "Describe what is in front of me."
            max_tokens = self.max_tokens
        img_b64 = encode_jpeg(frame_bgr, self.max_edge)
        full = ""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": user_text},
                ],
            }],
        ) as stream:
            for chunk in stream.text_stream:
                full += chunk
                if on_update:
                    on_update(full.strip())
        full = full.strip()
        if speaker and full:
            speaker.say(full)   # one utterance; period_pause config controls pacing
        return full
