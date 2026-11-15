"""Hostile offline tests for QA-only font installation. NO font files committed."""

import io
import zipfile

import pytest

from scripts.qa_install_opengost_release import verified_type_a_from_archive


def _archive(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as packed:
        for name, content in files:
            packed.writestr(name, content)
    return data.getvalue()


def test_bad_zip_is_rejected():
    with pytest.raises(ValueError, match="QA_GOST_RELEASE_ARCHIVE_INVALID"):
        verified_type_a_from_archive(b"this is not the release ZIP")


def test_type_b_never_substitutes_for_true_gost_type_a():
    data = _archive([("OpenGostTypeB-Regular.ttf", b"OTTO-but-not-TypeA")])
    with pytest.raises(ValueError, match="QA_GOST_RELEASE_NO_TYPE_A"):
        verified_type_a_from_archive(data)


def test_fake_type_a_cannot_bypass_exact_sha256():
    data = _archive([("OpenGostTypeA-Regular.ttf", b"OTTO-forged-font")])
    with pytest.raises(
        ValueError, match="QA_GOST_TYPE_A_SHA256_MISMATCH_OR_AMBIGUOUS"
    ):
        verified_type_a_from_archive(data)


def test_modified_type_a_plus_valid_type_b_never_gets_selected():
    data = _archive([
        ("OpenGostTypeA-Regular.ttf", b"OTTO-fake"),
        ("OpenGostTypeB-Regular.ttf", b"OTTO-other"),
    ])
    with pytest.raises(
        ValueError, match="QA_GOST_TYPE_A_SHA256_MISMATCH_OR_AMBIGUOUS"
    ):
        verified_type_a_from_archive(data)


def test_empty_archive_cannot_become_installed_face():
    with pytest.raises(ValueError, match="QA_GOST_RELEASE_NO_TYPE_A"):
        verified_type_a_from_archive(_archive([]))
