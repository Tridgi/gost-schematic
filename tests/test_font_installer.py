"""Select licensed Type A release assets without Type B or arbitrary file writes."""

import io
import zipfile

import pytest

from scripts.install_opengost_type_a import _get, select_font_asset


def test_direct_release_asset_preferred_over_zip():
    assets = [
        {"name": "OpenGOST-TypeB.ttf", "browser_download_url": "https://test/type-b"},
        {"name": "OpenGOST-TypeA.ttf", "browser_download_url": "https://test/type-a"},
        {"name": "Archive.zip", "browser_download_url": "https://test/all"},
    ]
    calls = []

    def getter(url):
        calls.append(url)
        return b"OTTOdata"

    name, data = select_font_asset(assets, getter)
    assert name == "OpenGOST-TypeA.ttf"
    assert data == b"OTTOdata"
    assert calls == ["https://test/type-a"]


def test_zip_asset_extracts_only_a_face():
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w") as bundle:
        bundle.writestr("fonts/OpenGOST-TypeB.ttf", b"type-b")
        bundle.writestr("fonts/OpenGOST-TypeA-Regular.ttf", b"type-a")
    assets = [{"name": "release.zip", "browser_download_url": "https://test/archive"}]
    name, data = select_font_asset(assets, lambda url: source.getvalue())
    assert name == "OpenGOST-TypeA-Regular.ttf"
    assert data == b"type-a"


def test_no_matching_face_fails_closed():
    with pytest.raises(ValueError, match="No OpenGOST Type A"):
        select_font_asset(
            [{"name": "TypeB.ttf", "browser_download_url": "https://test/type-b"}],
            lambda url: b"bad",
        )



def test_authenticated_release_request_never_leaks_token_to_asset_host(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-only")
    recorded = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"font-bytes"

    def capture(request, timeout=30):
        recorded.append((request.full_url, dict(request.header_items())))
        return Response()

    monkeypatch.setattr(
        "scripts.install_opengost_type_a.urllib.request.urlopen", capture,
    )
    assert _get("https://api.github.com/repos/ingenium-am/open-gost-arm/releases") == (
        b"font-bytes"
    )
    assert _get("https://github.com/ingenium-am/open-gost-arm/releases/asset") == (
        b"font-bytes"
    )
    assert recorded[0][1].get("Authorization") == "Bearer unit-test-only"
    assert "Authorization" not in recorded[1][1]


def test_anonymous_font_lookup_does_not_attach_authorization(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    collected = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"release"

    def capture(request, timeout=30):
        collected.append(dict(request.header_items()))
        return Response()

    monkeypatch.setattr(
        "scripts.install_opengost_type_a.urllib.request.urlopen", capture,
    )
    assert _get("https://api.github.com/repos/ingenium-am/open-gost-arm") == b"release"
    assert "Authorization" not in collected[0]
