# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import httpx

from app.services import net


def test_local_addresses_bypass_proxy():
    for url in (
        "http://127.0.0.1:11434/api/chat",
        "http://localhost:8080/v1/models",
        "http://192.168.88.100:8080/v1",
        "http://10.0.0.5:8080",
        "http://172.16.4.2:8080",
        "http://[::1]:8080",
        "http://kiwix.local:8080",
    ):
        assert net.is_lan_url(url), url
        assert net.client_options(url) == {"trust_env": False}, url


def test_public_addresses_keep_proxy():
    for url in (
        "https://api.telegram.org/bot123/getMe",
        "https://github.com/kent911/zelvera.git",
        "https://api.openai.com/v1",
        "http://8.8.8.8/",
    ):
        assert not net.is_lan_url(url), url
        assert net.client_options(url) == {}, url


def test_force_proxy_flag(monkeypatch):
    monkeypatch.setattr(net, "FORCE_PROXY_FOR_LAN", True)
    assert net.client_options("http://192.168.88.100:8080") == {}


def test_async_client_builds(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://192.168.88.100:10808")
    monkeypatch.setenv("HTTPS_PROXY", "http://192.168.88.100:10808")
    client = net.async_client("http://192.168.88.100:8080/v1", timeout=5)
    assert isinstance(client, httpx.AsyncClient)
    assert client._trust_env is False


def test_openai_client_bypasses_proxy_for_lan(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(llm.settings_store, "openai_base_url", lambda: "http://192.168.88.100:8080/v1")
    monkeypatch.setattr(llm.settings_store, "openai_api_key", lambda: "local")
    client = llm._openai_client()
    assert client._client._trust_env is False


def test_openai_client_keeps_proxy_for_public(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(llm.settings_store, "openai_base_url", lambda: "https://api.openai.com/v1")
    monkeypatch.setattr(llm.settings_store, "openai_api_key", lambda: "sk-test")
    client = llm._openai_client()
    assert client._client._trust_env is True
