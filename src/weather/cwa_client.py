"""CWA Open Data API client with caching."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from weather.cache import TtlCache
from weather.dataset_mapping import (
    get_dataset_id,
    get_all_county_names,
    normalize_county_name,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"


class CwaClient:
    """Async client for CWA weather forecast API."""

    def __init__(self, api_key: str, cache: TtlCache):
        self.api_key = api_key
        self.cache = cache

    async def get_weekly_forecast(
        self, county: str, district: str | None = None
    ) -> dict[str, Any]:
        """Get 1-week weather forecast for a county/district.

        Args:
            county: County/city name (e.g., 臺北市, 台北市, 台北)
            district: Optional district/township name (e.g., 中山區)

        Returns:
            Formatted forecast data dict
        """
        normalized = normalize_county_name(county)
        if not normalized:
            return {
                "error": True,
                "message": f"找不到縣市「{county}」。可用的縣市：{', '.join(get_all_county_names())}",
            }

        dataset_id = get_dataset_id(county)
        if not dataset_id:
            return {"error": True, "message": f"無法取得「{normalized}」的資料集 ID"}

        # Check cache
        raw_data = self.cache.get(dataset_id)
        if raw_data is None:
            raw_data = await self._fetch_api(dataset_id)
            if "error" in raw_data:
                return raw_data
            self.cache.set(dataset_id, raw_data)

        return self._format_response(raw_data, normalized, district)

    async def _fetch_api(self, dataset_id: str) -> dict[str, Any]:
        """Fetch data from CWA API."""
        url = f"{BASE_URL}/{dataset_id}"
        params = {"Authorization": self.api_key}

        logger.info(f"Fetching CWA API: {dataset_id}")
        try:
            # CWA API certificate has a known issue with missing Subject Key Identifier
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("success") != "true":
                return {"error": True, "message": "CWA API 回應失敗"}

            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"CWA API HTTP error: {e.response.status_code}")
            return {"error": True, "message": f"CWA API 錯誤: {e.response.status_code}"}
        except httpx.RequestError as e:
            logger.error(f"CWA API request error: {e}")
            return {"error": True, "message": f"CWA API 連線失敗: {e}"}

    def _format_response(
        self, data: dict, county: str, district: str | None
    ) -> dict[str, Any]:
        """Format raw CWA API response into structured output."""
        try:
            locations_list = data["records"]["Locations"]
            if not locations_list:
                return {"error": True, "message": "無預報資料"}

            locations = locations_list[0]
            all_districts = locations.get("Location", [])

            if district:
                # Filter to specific district
                matched = [
                    loc for loc in all_districts if loc["LocationName"] == district
                ]
                if not matched:
                    available = [loc["LocationName"] for loc in all_districts]
                    return {
                        "error": True,
                        "message": f"找不到「{county} {district}」。「{county}」可用的鄉鎮區：{', '.join(available)}",
                    }
                districts_to_format = matched
            else:
                districts_to_format = all_districts

            result_parts = []
            for loc in districts_to_format:
                result_parts.append(
                    self._format_district_forecast(county, loc)
                )

            return {
                "county": county,
                "district": district,
                "forecast": "\n\n".join(result_parts),
            }
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing CWA response: {e}")
            return {"error": True, "message": f"解析 CWA 回應失敗: {e}"}

    def _format_district_forecast(self, county: str, location: dict) -> str:
        """Format forecast for a single district."""
        district_name = location["LocationName"]
        elements = location.get("WeatherElement", [])

        # Build element lookup: ElementName → time series
        elem_map: dict[str, list] = {}
        for elem in elements:
            elem_map[elem["ElementName"]] = elem.get("Time", [])

        header = f"=== {county} {district_name} 一週天氣預報 ==="
        periods = []

        # Use weather description time series as the primary timeline
        wx_times = elem_map.get("天氣現象", [])
        temp_times = elem_map.get("平均溫度", [])
        max_t_times = elem_map.get("最高溫度", [])
        min_t_times = elem_map.get("最低溫度", [])
        pop_times = elem_map.get("12小時降雨機率", [])
        rh_times = elem_map.get("平均相對濕度", [])
        desc_times = elem_map.get("天氣預報綜合描述", [])
        ci_times = elem_map.get("最大舒適度指數", [])
        uvi_times = elem_map.get("紫外線指數", [])
        wind_speed_times = elem_map.get("風速", [])
        wind_dir_times = elem_map.get("風向", [])
        at_max_times = elem_map.get("最高體感溫度", [])
        at_min_times = elem_map.get("最低體感溫度", [])

        # Determine the primary timeline (use the longest available)
        primary_times = desc_times or wx_times or temp_times
        if not primary_times:
            return f"{header}\n（無預報資料）"

        for i, time_entry in enumerate(primary_times):
            start = time_entry.get("StartTime", "")
            end = time_entry.get("EndTime", "")

            lines = [f"【{start} ~ {end}】"]

            # Weather condition
            wx_val = self._get_element_value(wx_times, i, "Weather")
            if wx_val:
                lines.append(f"  天氣: {wx_val}")

            # Temperature
            temp_val = self._get_element_value(temp_times, i, "Temperature")
            if temp_val:
                lines.append(f"  溫度: {temp_val}°C")

            # Max/Min temperature
            max_t = self._get_element_value(max_t_times, i, "MaxTemperature")
            min_t = self._get_element_value(min_t_times, i, "MinTemperature")
            if max_t and min_t:
                lines.append(f"  最高溫/最低溫: {max_t}°C / {min_t}°C")

            # Apparent temperature
            at_max = self._get_element_value(at_max_times, i, "MaxAT")
            at_min = self._get_element_value(at_min_times, i, "MinAT")
            if at_max and at_min:
                lines.append(f"  體感溫度: {at_min}°C ~ {at_max}°C")

            # Rain probability
            pop_val = self._get_element_value(pop_times, i, "PoP12h")
            if pop_val:
                lines.append(f"  降雨機率: {pop_val}%")

            # Humidity
            rh_val = self._get_element_value(rh_times, i, "RH")
            if rh_val:
                lines.append(f"  相對濕度: {rh_val}%")

            # Wind
            wind_speed = self._get_element_value(wind_speed_times, i, "WindSpeed")
            wind_dir = self._get_element_value(wind_dir_times, i, "WindDirection")
            if wind_speed and wind_dir:
                lines.append(f"  風向/風速: {wind_dir} {wind_speed}")

            # Comfort index
            ci_val = self._get_element_value(ci_times, i, "MaxCI")
            if ci_val:
                lines.append(f"  舒適度: {ci_val}")

            # UV index
            uvi_val = self._get_element_value(uvi_times, i, "UVI")
            if uvi_val:
                lines.append(f"  紫外線指數: {uvi_val}")

            # Description
            desc_val = self._get_element_value(desc_times, i, "WeatherDescription")
            if desc_val:
                lines.append(f"  描述: {desc_val}")

            periods.append("\n".join(lines))

        return header + "\n\n" + "\n\n".join(periods)

    @staticmethod
    def _get_element_value(
        time_series: list, index: int, fallback_key: str = ""
    ) -> str | None:
        """Safely extract a value from a time series entry."""
        if not time_series or index >= len(time_series):
            return None
        entry = time_series[index]
        element_values = entry.get("ElementValue", [])
        if not element_values:
            return None
        # Return the first non-empty value
        for ev in element_values:
            for key, val in ev.items():
                if val and val.strip():
                    return val.strip()
        return None
