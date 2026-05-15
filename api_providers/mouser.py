import requests
from typing import Dict, Optional
from .base import BaseProvider


class MouserProvider(BaseProvider):
    """Mouser Search API v2 implementation."""

    BASE_URL = "https://api.mouser.com/api/v2/search/partnumber"

    def search_mpn(self, mpn: str) -> Optional[Dict[str, str]]:
        """Searches for an MPN and returns technical attributes."""
        url = f"{self.BASE_URL}?key={self.api_key}"
        payload = {
            "SearchByPartRequest": {
                "mouserPartNumber": "",  # We use manufacturerPartNumber instead
                "manufacturerPartNumber": mpn,
                "partSearchOptions": "None",
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            parts = data.get("SearchResults", {}).get("Parts", [])
            if not parts:
                return None

            # Use the first exact match if possible
            best_match = parts[0]

            return self._normalize_attributes(best_match)

        except Exception:
            # For a production tool, we might want more detailed logging here
            return None

    def _normalize_attributes(self, mouser_part: Dict) -> Dict[str, str]:
        """Normalizes Mouser part attributes into a standard dictionary."""
        normalized = {
            "Description": mouser_part.get("Description", ""),
            "Manufacturer": mouser_part.get("Manufacturer", ""),
            "MPN": mouser_part.get("ManufacturerPartNumber", ""),
        }

        # Add technical attributes
        attributes = mouser_part.get("ProductAttributes", [])
        for attr in attributes:
            name = attr.get("AttributeName")
            value = attr.get("AttributeValue")
            if name and value:
                normalized[name] = value

        return normalized
