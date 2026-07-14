"""Guards on the shared release/identity constants (pursuit.shared.version)."""

import re

from pursuit.shared import version


def test_exposes_every_documented_constant() -> None:
    for name in (
        "__version__",
        "BOOK_VERSION",
        "COURSE",
        "GROUP_ID",
        "GROUP_NAME",
        "MEMBERS",
        "LICENSE_NOTICE",
    ):
        assert hasattr(version, name), f"version.py must expose {name}"


def test_group_id_is_the_submission_identity() -> None:
    assert version.GROUP_ID == "nis-yar1"
    assert version.GROUP_NAME == "Nis-Yar-1"
    assert set(version.MEMBERS) == {"Nissim Deri", "Yarden Tziar"}


def test_versions_are_dotted_release_strings() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert version.BOOK_VERSION == "3.0.0"


def test_course_and_license_are_nonempty_prose() -> None:
    assert "Yoram Segal" in version.COURSE
    assert "MIT" in version.LICENSE_NOTICE


def test_all_lists_only_real_attributes() -> None:
    for name in version.__all__:
        assert hasattr(version, name)
