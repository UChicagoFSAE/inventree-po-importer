import requests
import json
import os
import time
from typing import Dict, Optional
from .base import BaseProvider


class DigiKeyProvider(BaseProvider):
    """DigiKey Part Search API implementation with OAuth2."""

    TOKEN_FILE = ".digikey_token.json"
    AUTH_URL = "https://api.digikey.com/v1/oauth2/authorize"
    TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
    SEARCH_URL = "https://api.digikey.com/v1/products/search"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_data = self._load_token()

    def search_mpn(self, mpn: str) -> Optional[Dict[str, str]]:
        """Searches for an MPN and returns technical attributes."""
        if not self._ensure_token():
            return None

        headers = {
            "X-DIGIKEY-Client-Id": self.client_id,
            "Authorization": f"Bearer {self.token_data['access_token']}",
            "Content-Type": "application/json",
        }

        payload = {"Keywords": mpn, "RecordCount": 1}

        try:
            response = requests.post(
                self.SEARCH_URL, json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            parts = data.get("Products", [])
            if not parts:
                return None

            return self._normalize_attributes(parts[0])

        except Exception:
            return None

    def _normalize_attributes(self, dk_part: Dict) -> Dict[str, str]:
        """Normalizes DigiKey part attributes."""
        normalized = {
            "Description": dk_part.get("Description", {}).get("ProductDescription", ""),
            "Manufacturer": dk_part.get("Manufacturer", {}).get("Value", ""),
            "MPN": dk_part.get("ManufacturerPartNumber", ""),
        }

        # Add technical parameters
        parameters = dk_part.get("Parameters", [])
        for param in parameters:
            name = param.get("Parameter")
            value = param.get("Value")
            if name and value:
                normalized[name] = value

        return normalized

    def _load_token(self) -> Optional[Dict]:
        """Loads cached token from file."""
        if os.path.exists(self.TOKEN_FILE):
            try:
                with open(self.TOKEN_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_token(self, data: Dict):
        """Saves token data to file."""
        data["expires_at"] = time.time() + data["expires_in"]
        self.token_data = data
        with open(self.TOKEN_FILE, "w") as f:
            json.dump(data, f)

    def _ensure_token(self) -> bool:
        """Ensures a valid access token is available, refreshing if needed."""
        if not self.token_data:
            return self._interactive_auth()

        # Buffer of 60 seconds
        if time.time() > self.token_data.get("expires_at", 0) - 60:
            return self._refresh_token()

        return True

    def _interactive_auth(self) -> bool:
        """Handles initial interactive OAuth2 flow."""
        print("\n--- DigiKey API Authorization Required ---")
        # Note: Redirect URI must match what's configured in DigiKey portal
        # Usually https://localhost for CLI apps
        redirect_uri = "https://localhost"
        auth_url = f"{self.AUTH_URL}?response_type=code&client_id={self.client_id}&redirect_uri={redirect_uri}"

        print(f"Please visit this URL to authorize the application:\n{auth_url}")
        code = input("\nEnter the 'code' parameter from the resulting URL: ").strip()

        if not code:
            return False

        payload = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(self.TOKEN_URL, data=payload, timeout=10)
            response.raise_for_status()
            self._save_token(response.json())
            return True
        except Exception as e:
            print(f"Error exchanging code: {e}")
            return False

    def _refresh_token(self) -> bool:
        """Refreshes the access token using the refresh token."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.token_data["refresh_token"],
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(self.TOKEN_URL, data=payload, timeout=10)
            response.raise_for_status()
            self._save_token(response.json())
            return True
        except Exception:
            # If refresh fails, try re-auth
            return self._interactive_auth()
