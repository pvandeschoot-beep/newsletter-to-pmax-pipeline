from pathlib import Path

import pytest
from PIL import Image

from pmax.images import fit_to_ratio, make_pmax_formats, overlay_logo
from pmax.render import render_handoff, write_review_csv
from pmax.validate import ERROR, has_errors, validate_campaign


def minimal_campaign(**overrides) -> dict:
    data = {
        "client": "Testklant",
        "campaign": "Test",
        "business_name": "Testklant",
        "logo": "brand/logo.png",
        "asset_groups": [
            {
                "name": "Thema",
                "final_url": "https://example.com/thema",
                "headlines": ["Een", "Twee", "Drie"],
                "long_headlines": ["Een lange headline"],
                "descriptions": ["Beschrijving een.", "Beschrijving twee."],
            }
        ],
    }
    data.update(overrides)
    return data


# --- tekstvalidatie -------------------------------------------------------

def test_minimal_campaign_passes():
    assert not has_errors(validate_campaign(minimal_campaign()))


def test_headline_over_30_chars_is_error():
    data = minimal_campaign()
    data["asset_groups"][0]["headlines"][0] = "x" * 31
    assert any(i.level == ERROR and "31 tekens" in i.message for i in validate_campaign(data))


def test_too_few_headlines_is_error():
    """De oude validator keek alleen naar maxlengte en miste dit volledig."""
    data = minimal_campaign()
    data["asset_groups"][0]["headlines"] = ["Een", "Twee"]
    assert any(i.level == ERROR and "minimaal 3" in i.message for i in validate_campaign(data))


def test_too_many_headlines_is_error():
    data = minimal_campaign()
    data["asset_groups"][0]["headlines"] = [f"H{i}" for i in range(16)]
    assert any(i.level == ERROR and "maximaal 15" in i.message for i in validate_campaign(data))


def test_single_description_is_error():
    data = minimal_campaign()
    data["asset_groups"][0]["descriptions"] = ["Slechts een."]
    assert any(i.level == ERROR and "minimaal 2" in i.message for i in validate_campaign(data))


def test_missing_business_name_is_error():
    data = minimal_campaign()
    del data["business_name"]
    assert any(i.field == "business_name" and i.level == ERROR for i in validate_campaign(data))


def test_business_name_over_25_chars_is_error():
    data = minimal_campaign(business_name="x" * 26)
    assert any(i.field == "business_name" and i.level == ERROR for i in validate_campaign(data))


def test_relative_landing_page_is_error():
    """Relatieve paden zonder client-resolve zijn ongeldig; PMax wil een absolute URL."""
    data = minimal_campaign()
    data["asset_groups"][0]["final_url"] = "/thema"
    assert any(i.field == "final_url" and i.level == ERROR for i in validate_campaign(data))


def test_duplicate_headline_is_warning():
    data = minimal_campaign()
    data["asset_groups"][0]["headlines"] = ["Een", "een", "Drie"]
    issues = validate_campaign(data)
    assert any(i.level == "warning" and "duplicaat" in i.message for i in issues)
    assert not has_errors(issues)


# --- beeldvalidatie -------------------------------------------------------

@pytest.fixture
def assets(tmp_path: Path) -> Path:
    (tmp_path / "brand").mkdir()
    Image.new("RGB", (1200, 1200), "white").save(tmp_path / "brand/logo.png")
    Image.new("RGB", (1200, 628), "blue").save(tmp_path / "landscape.png")
    Image.new("RGB", (1200, 1200), "blue").save(tmp_path / "square.png")
    Image.new("RGB", (800, 600), "red").save(tmp_path / "wrong_ratio.png")
    return tmp_path


def test_correct_images_pass(assets: Path):
    data = minimal_campaign()
    data["asset_groups"][0]["images"] = {
        "landscape": ["landscape.png"],
        "square": ["square.png"],
    }
    assert not has_errors(validate_campaign(data, asset_root=assets))


def test_wrong_aspect_ratio_is_error(assets: Path):
    data = minimal_campaign()
    data["asset_groups"][0]["images"] = {
        "landscape": ["wrong_ratio.png"],
        "square": ["square.png"],
    }
    issues = validate_campaign(data, asset_root=assets)
    assert any("ASPECT_RATIO_NOT_ALLOWED" in i.message for i in issues)


def test_missing_square_image_is_error(assets: Path):
    data = minimal_campaign()
    data["asset_groups"][0]["images"] = {"landscape": ["landscape.png"]}
    issues = validate_campaign(data, asset_root=assets)
    assert any(i.field == "square" and i.level == ERROR for i in issues)


# --- beeldpijplijn --------------------------------------------------------

def test_fit_to_ratio_returns_exact_dimensions():
    assert fit_to_ratio(Image.new("RGB", (3000, 1000)), 1200, 1200).size == (1200, 1200)


def test_fit_to_ratio_crops_from_center():
    img = Image.new("RGB", (300, 100), "black")
    img.putpixel((150, 50), (255, 0, 0))
    assert fit_to_ratio(img, 100, 100).getpixel((50, 50)) == (255, 0, 0)


def test_overlay_logo_runs_and_keeps_size():
    """Regressietest: de oude apply_logo_overlay.py gaf hier een TypeError."""
    base = Image.new("RGB", (1200, 628), "blue")
    logo = Image.new("RGBA", (300, 100), (255, 0, 0, 255))
    out = overlay_logo(base, logo)
    assert out.size == (1200, 628)
    assert out.mode == "RGB"


def test_make_pmax_formats_produces_all_ratios(assets: Path, tmp_path: Path):
    out_dir = tmp_path / "out"
    made = make_pmax_formats(assets / "landscape.png", out_dir, "thema", logo=assets / "brand/logo.png")
    assert set(made) == {"landscape", "square", "portrait"}
    for paths in made.values():
        assert len(paths) == 2  # met en zonder logo
        assert all(p.exists() for p in paths)


def test_generated_images_pass_validation(assets: Path, tmp_path: Path):
    """De output van de beeldpijplijn moet per definitie door de validator komen."""
    out_dir = tmp_path / "out"
    made = make_pmax_formats(assets / "landscape.png", out_dir, "thema")
    data = minimal_campaign()
    data["asset_groups"][0]["images"] = {
        slot: [str(p.relative_to(tmp_path)) for p in paths] for slot, paths in made.items()
    }
    data["logo"] = "brand/logo.png"
    (tmp_path / "brand").mkdir(exist_ok=True)
    Image.new("RGB", (1200, 1200), "white").save(tmp_path / "brand/logo.png")
    assert not has_errors(validate_campaign(data, asset_root=tmp_path))


# --- render ---------------------------------------------------------------

def test_handoff_mentions_disclaimer_and_all_groups():
    data = minimal_campaign()
    data["asset_groups"].append({**data["asset_groups"][0], "name": "Tweede"})
    text = render_handoff(data, drive_link="https://drive.example.com/x")
    assert "ter review" in text
    assert "Thema" in text and "Tweede" in text
    assert "https://drive.example.com/x" in text


def test_review_csv_has_row_per_text_asset(tmp_path: Path):
    out = write_review_csv(minimal_campaign(), tmp_path / "review.csv")
    rows = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1 + 3 + 1 + 2  # header + headlines + long + descriptions


def test_yaml_colon_trap_is_caught():
    """Regressie: in de originele copy.yaml werd een description met ': ' door
    YAML als dict geparsed. De oude len()-check zag dat niet."""
    data = minimal_campaign()
    data["asset_groups"][0]["descriptions"] = [
        {"Luxe of budget": "wij regelen het voor je."},
        "Een geldige beschrijving.",
    ]
    issues = validate_campaign(data)
    assert any(i.level == ERROR and "geen tekst maar dict" in i.message for i in issues)
