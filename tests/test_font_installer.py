"""Select licensed Type A release assets without Type B or arbitrary file writes."""

import hashlib
import io
import json
import zipfile

import pytest

from scripts import install_opengost_type_a as installer
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



def _zip_type_a(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("OpenGOSTtypeB-Regular.ttf", b"wrong-type-b")
        archive.writestr("OpenGOSTtypeA-Regular.ttf", payload)
    return buffer.getvalue()


def test_offline_second_install_recovers_original_pinned_face_from_verified_cache(
    tmp_path, monkeypatch,
):
    face = b"OTTO" + b"original licensed v0.7 type A positive fixture"
    expected = hashlib.sha256(face).hexdigest()
    calls = []

    def first_get(url):
        calls.append(url)
        assert url == installer.RELEASE_ASSET
        return _zip_type_a(face)

    monkeypatch.setattr(installer, "_get", first_get)
    path, digest, source = installer.install_type_a(
        tmp_path, expected_sha256=expected
    )
    assert path.name == installer.CACHED_FACE
    assert digest == expected
    assert source == "PINNED_UPSTREAM_V0.7_RELEASE"
    assert path.read_bytes() == face
    assert calls == [installer.RELEASE_ASSET]

    def offline(_):
        raise AssertionError("Offline hash-verified cache should never fetch")

    monkeypatch.setattr(installer, "_get", offline)
    again, digest, source = installer.install_type_a(
        tmp_path, expected_sha256=expected
    )
    assert again == path and digest == expected
    assert source == "LOCAL_HASH_VERIFIED_CACHE"


def test_pin_release_direct_403_recovers_from_authenticated_api(monkeypatch, tmp_path):
    face = b"OTTOcorrect-v0.7-original"
    expected = hashlib.sha256(face).hexdigest()
    asset_url = "https://github.com/ingenium-am/open-gost-arm/releases/download/v0.7/release.zip"
    calls = []

    def get(url):
        calls.append(url)
        if url == installer.RELEASE_ASSET:
            raise OSError("HTTP Error 403: upstream CDN temporarily unavailable")
        if url == installer.RELEASE:
            return json.dumps({
                "tag_name": "v0.7",
                "assets": [{
                    "name": "OpenGOST_TTF_0.7.zip",
                    "browser_download_url": asset_url,
                }],
            }).encode()
        assert url == asset_url
        return _zip_type_a(face)

    monkeypatch.setattr(installer, "_get", get)
    file, digest, origin = installer.install_type_a(
        tmp_path, expected_sha256=expected
    )
    assert file.read_bytes() == face
    assert digest == expected and origin == "PINNED_UPSTREAM_V0.7_RELEASE"
    assert calls == [installer.RELEASE_ASSET, installer.RELEASE, asset_url]


def test_unlicensed_or_swapped_face_cannot_pass_known_sha(monkeypatch, tmp_path):
    original = b"OTTO" + b"licensed-v0.7-expected"
    wrong = b"OTTO" + b"non-original-or-type-b-impersonation"
    monkeypatch.setattr(installer, "_get", lambda _: _zip_type_a(wrong))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        installer.install_type_a(
            tmp_path, expected_sha256=hashlib.sha256(original).hexdigest()
        )
    assert not list(tmp_path.iterdir())


def test_corrupted_cached_font_fails_closed_even_if_network_works(monkeypatch, tmp_path):
    cached = tmp_path / installer.CACHED_FACE
    cached.write_bytes(b"OTTOtampered-cached-face")
    monkeypatch.setattr(
        installer, "_get", lambda _: pytest.fail("Must not re-fetch silently")
    )
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        installer.install_type_a(
            tmp_path,
            expected_sha256=hashlib.sha256(b"OTTOcorrect").hexdigest(),
        )
    assert cached.read_bytes() == b"OTTOtampered-cached-face"


def test_metadata_tag_swap_and_double_403_rejected_no_substitute(monkeypatch, tmp_path):
    def get(url):
        if url == installer.RELEASE_ASSET:
            raise OSError("403")
        if url == installer.RELEASE:
            return json.dumps({"tag_name": "v0.8", "assets": []}).encode()
        raise AssertionError(url)

    monkeypatch.setattr(installer, "_get", get)
    with pytest.raises(OSError, match="Unexpected OpenGOST release tag"):
        installer.install_type_a(tmp_path)
    assert not list(tmp_path.iterdir())

    monkeypatch.setattr(
        installer, "_get", lambda _: (_ for _ in ()).throw(OSError("403"))
    )
    with pytest.raises(OSError, match="pinned asset unavailable"):
        installer.install_type_a(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("invalid", ["", "deadbeef", "z" * 64, "1" * 65])
def test_font_sha_contract_rejects_invalid_digest(invalid, tmp_path):
    with pytest.raises(ValueError, match="64-character hex"):
        installer.install_type_a(tmp_path, expected_sha256=invalid)
