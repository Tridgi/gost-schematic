"""Select licensed Type A release assets without Type B or arbitrary file writes."""

import io
import zipfile

import pytest

from scripts.install_opengost_type_a import select_font_asset


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
