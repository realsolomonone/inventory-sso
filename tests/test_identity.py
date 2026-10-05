import pytest

from src.identity import lookup_catalog, select_profiles
from src.models import CatalogAccount


def test_select_profiles_skips_non_sso():
    selected = select_profiles(
        ["edl-uat", "static-keys", "edl-prod"],
        requested=None,
        exclude=["edl-prod"],
        sso_only=True,
        is_sso=lambda name: name.startswith("edl-"),
    )
    assert selected == ["edl-uat"]


def test_select_profiles_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown profile"):
        select_profiles(
            ["edl-uat"],
            requested=["missing"],
            exclude=[],
            sso_only=False,
            is_sso=lambda _name: True,
        )


def test_lookup_catalog_by_alias_and_id():
    catalog = [
        CatalogAccount(name="edl-uat", account_id="111", aliases=["edl-uat-alias"], environment="uat"),
    ]
    assert lookup_catalog(catalog, profile="edl-uat-alias", account_id="").environment == "uat"
    assert lookup_catalog(catalog, profile="other", account_id="111").name == "edl-uat"
