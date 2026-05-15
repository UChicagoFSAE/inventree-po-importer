from typing import Dict, Optional


class BaseProvider:
    """Base class for external part API providers."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_mpn(self, mpn: str) -> Optional[Dict[str, str]]:
        """
        Searches for an MPN and returns a dictionary of technical parameters.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement search_mpn")
