# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
import sys
import types

from app.services import voice


def test_synthesize_passes_proxy(monkeypatch):
    captured: dict = {}

    class FakeCommunicate:
        def __init__(self, text, voice_name, proxy=None):
            captured["text"] = text
            captured["proxy"] = proxy

        async def stream(self):
            yield {"type": "audio", "data": b"abc"}
            yield {"type": "WordBoundary"}

    fake = types.SimpleNamespace(Communicate=FakeCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake)
    monkeypatch.setattr(voice, "tts_available", lambda: True)

    result = asyncio.run(
        voice.synthesize("привет", "ru-RU-DmitryNeural", proxy="socks5://127.0.0.1:1080")
    )

    assert result == b"abc"
    assert captured["proxy"] == "socks5://127.0.0.1:1080"


def test_synthesize_empty_for_blank_text(monkeypatch):
    monkeypatch.setattr(voice, "tts_available", lambda: True)
    assert asyncio.run(voice.synthesize("   ")) == b""
