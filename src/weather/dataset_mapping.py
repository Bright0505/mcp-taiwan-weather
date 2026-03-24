"""County name to CWA dataset ID mapping for 1-week forecasts."""

from __future__ import annotations

# Verified mapping: county/city name → F-D0047 dataset ID (1-week forecast)
COUNTY_DATASET_MAP: dict[str, str] = {
    "宜蘭縣": "F-D0047-003",
    "桃園市": "F-D0047-007",
    "新竹縣": "F-D0047-011",
    "苗栗縣": "F-D0047-015",
    "彰化縣": "F-D0047-019",
    "南投縣": "F-D0047-023",
    "雲林縣": "F-D0047-027",
    "嘉義縣": "F-D0047-031",
    "屏東縣": "F-D0047-035",
    "臺東縣": "F-D0047-039",
    "花蓮縣": "F-D0047-043",
    "澎湖縣": "F-D0047-047",
    "基隆市": "F-D0047-051",
    "新竹市": "F-D0047-055",
    "嘉義市": "F-D0047-059",
    "臺北市": "F-D0047-063",
    "高雄市": "F-D0047-067",
    "新北市": "F-D0047-071",
    "臺中市": "F-D0047-075",
    "臺南市": "F-D0047-079",
    "連江縣": "F-D0047-083",
    "金門縣": "F-D0047-087",
}

# 台 → 臺 conversion map
_SIMPLIFY_TO_TRADITIONAL: dict[str, str] = {
    "台": "臺",
}

# Common suffixes for counties/cities
_COUNTY_SUFFIXES = ["市", "縣"]


def normalize_county_name(name: str) -> str | None:
    """Normalize county name to match COUNTY_DATASET_MAP keys.

    Handles:
    - 台 vs 臺 variants (e.g., 台北市 → 臺北市)
    - Missing suffix (e.g., 台北 → 臺北市)
    """
    # Replace 台 with 臺
    normalized = name.replace("台", "臺")

    # Direct match
    if normalized in COUNTY_DATASET_MAP:
        return normalized

    # Try adding suffix
    for suffix in _COUNTY_SUFFIXES:
        candidate = normalized + suffix
        if candidate in COUNTY_DATASET_MAP:
            return candidate

    return None


def get_dataset_id(county_name: str) -> str | None:
    """Get dataset ID for a county name (with normalization)."""
    normalized = normalize_county_name(county_name)
    if normalized:
        return COUNTY_DATASET_MAP[normalized]
    return None


def get_all_county_names() -> list[str]:
    """Return all available county/city names."""
    return list(COUNTY_DATASET_MAP.keys())
