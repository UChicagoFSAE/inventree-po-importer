from typing import List, Dict, Optional
import os
from models import LineItem
from inventree.company import SupplierPart, ManufacturerPart, Company
from inventree.part import Part, PartCategory, PartParameter
from api_providers.base import BaseProvider
from conventions import NamingConvention


class Resolver:
    def __init__(self, api):
        self.api = api
        self.part_cache: Dict[int, Part] = {}
        self.providers: List[BaseProvider] = self._load_providers()

    def _load_providers(self) -> List[BaseProvider]:
        """Loads available API providers based on environment variables."""
        providers = []
        # Mouser implementation
        mouser_key = os.getenv("MOUSER_API_KEY")
        if mouser_key:
            mouser_key = mouser_key.strip()
            from api_providers.mouser import MouserProvider

            providers.append(MouserProvider(mouser_key))

        # DigiKey implementation
        dk_id = os.getenv("DIGIKEY_CLIENT_ID")
        dk_secret = os.getenv("DIGIKEY_CLIENT_SECRET")
        if dk_id and dk_secret:
            from api_providers.digikey import DigiKeyProvider

            providers.append(DigiKeyProvider(dk_id, dk_secret))

        return providers

    def resolve_items(self, items: List[LineItem], supplier_id: int):
        """Enriches a list of LineItems with InvenTree PKs."""
        for item in items:
            self.resolve_item(item, supplier_id)

    def search_parts(self, query: str, limit: int = 5) -> List[Part]:
        """Search for parts in InvenTree."""
        return Part.list(self.api, search=query, limit=limit)

    def search_categories(self, query: str, limit: int = 5) -> List[PartCategory]:
        """Search for part categories in InvenTree."""
        return PartCategory.list(self.api, search=query, limit=limit)

    def search_manufacturers(self, query: str, limit: int = 5) -> List[Company]:
        """Search for companies that are manufacturers."""
        return Company.list(self.api, search=query, is_manufacturer=True, limit=limit)

    def create_manufacturer(self, name: str) -> Company:
        """Create a new manufacturer company."""
        return Company.create(self.api, data={"name": name, "is_manufacturer": True})

    def create_new_part(
        self,
        item: LineItem,
        name: str,
        description: str,
        category_pk: int,
        supplier_id: int,
        manufacturer_pk: Optional[int] = None,
        parameters: Optional[Dict[str, str]] = None,
    ) -> int:
        """Create a new Part and associated linkage."""
        # 1. Create Base Part
        part_data = {
            "name": name,
            "description": description,
            "category": category_pk,
            "active": True,
        }
        new_part = Part.create(self.api, data=part_data)
        if isinstance(new_part, list):
            new_part = new_part[0]

        # 2. Add Part Parameters if provided
        if parameters:
            # We first need to get the parameter templates for this category
            # In a real implementation, we'd map our API keys to InvenTree templates
            for key, value in parameters.items():
                try:
                    PartParameter.create(
                        self.api,
                        data={
                            "part": new_part.pk,
                            "template": key,  # InvenTree expects a template ID or name
                            "data": value,
                        },
                    )
                except Exception:
                    # If template doesn't exist, we skip it for now
                    pass

        # 3. Link Manufacturer Part if manufacturer provided
        manufacturer_part_pk = None
        if manufacturer_pk:
            mp_data = {
                "part": new_part.pk,
                "manufacturer": manufacturer_pk,
                "MPN": item.mpn,
            }
            new_mp = ManufacturerPart.create(self.api, data=mp_data)
            if isinstance(new_mp, list):
                new_mp = new_mp[0]
            manufacturer_part_pk = new_mp.pk

        # 3. Create Supplier Part
        sp_data = {
            "part": new_part.pk,
            "supplier": supplier_id,
            "SKU": item.sku,
            "manufacturer_part": manufacturer_part_pk,
        }
        new_sp = SupplierPart.create(self.api, data=sp_data)
        if isinstance(new_sp, list):
            new_sp = new_sp[0]

        # Store supplier_part_pk in item for stock creation
        item.supplier_part_pk = new_sp.pk

        return new_part.pk

    def link_manual_part(
        self, item: LineItem, part_pk: int, status_message: str = "Resolved (Manual)"
    ):
        """Manually link an item to a part and fetch metadata."""
        item.base_part_pk = part_pk
        item.resolution_status = status_message
        self._fetch_part_metadata(item)

    def _fetch_part_metadata(self, item: LineItem):
        """Fetches part name and description if a base_part_pk is present."""
        if not item.base_part_pk:
            return

        if item.base_part_pk in self.part_cache:
            p = self.part_cache[item.base_part_pk]
        else:
            p = Part(self.api, pk=item.base_part_pk)
            self.part_cache[item.base_part_pk] = p

        item.part_name = getattr(p, "name", "N/A")
        item.part_description = getattr(p, "description", "N/A")
        item.internal_part_number = getattr(p, "IPN", "---")

    def _fetch_external_parameters(self, mpn: str) -> Dict[str, str]:
        """Queries available external providers for part parameters."""
        for provider in self.providers:
            params = provider.search_mpn(mpn)
            if params:
                return params
        return {}

    def resolve_by_parameters(self, item: LineItem) -> Optional[int]:
        """Attempts to find a base part by matching fetched parameters to InvenTree."""
        # 1. Fetch parameters if not already present
        if not item.api_parameters:
            item.api_parameters = self._fetch_external_parameters(item.mpn)

        if not item.api_parameters:
            return None

        # 2. Fast-track check (e.g. Passives)
        fast_track_keywords = ["CAP", "RES", "INDUCTOR", "SWITCH", "LED"]
        description = (item.description or "").upper()
        is_fast_track = any(kw in description for kw in fast_track_keywords)

        if not is_fast_track:
            # Queue for manual review instead of auto-resolving complex parts
            item.resolution_status = "Pending Manual Review (Complex)"
            return None

        # 3. Parametric Search
        # Try naming convention first
        suggested_name = NamingConvention.suggest_name(item.api_parameters)
        if suggested_name:
            matches = self.search_parts(suggested_name, limit=1)
            if matches:
                return matches[0].pk

        # Fallback to keyword search
        # We look for the most identifying parameters (Capacitance/Resistance + Package)
        # Using a broader list of keys to catch both Mouser and DigiKey variations
        identifying_keys = [
            "Capacitance",
            "Resistance",
            "Inductance",
            "Package / Case",
            "Package",
            "Case Code - in",
            "Case Code - mm",
            "Case/Package",
        ]
        search_terms = []
        for key in identifying_keys:
            if key in item.api_parameters:
                val = item.api_parameters[key]
                # Clean up values: e.g. "0603 (1608 Metric)" -> "0603"
                if "(" in val:
                    val = val.split("(")[0].strip()
                search_terms.append(val)

        if not search_terms:
            return None

        # Perform a keyword search using the technical parameters
        query = " ".join(search_terms)
        potential_parts = self.search_parts(query, limit=5)

        # If we find exactly one match, we auto-resolve it
        if len(potential_parts) == 1:
            return potential_parts[0].pk

        return None

    def resolve_item(self, item: LineItem, supplier_id: int):
        # 1. Try SKU match (SupplierPart)
        try:
            # Note: InvenTree API list() returns a list of objects
            supplier_parts = SupplierPart.list(
                self.api, SKU=item.sku, supplier=supplier_id
            )

            if supplier_parts:
                sp = supplier_parts[0]
                item.supplier_part_pk = sp.pk
                item.base_part_pk = sp.part
                item.resolution_status = "Resolved (SKU)"
                self._fetch_part_metadata(item)
                return

            # 2. Try MPN match (ManufacturerPart)
            manufacturer_parts = ManufacturerPart.list(self.api, MPN=item.mpn)

            if manufacturer_parts:
                mp = manufacturer_parts[0]
                item.base_part_pk = mp.part
                item.resolution_status = "Resolved (MPN)"
                self._fetch_part_metadata(item)
                # Note: supplier_part_pk remains None as it's not a direct supplier match
                return

            # 3. Always attempt API fetch for metadata/parameters if not already present
            if not item.api_parameters:
                item.api_parameters = self._fetch_external_parameters(item.mpn)

            # 4. Try Parameter Match (API Fallback) for fast-track items
            part_pk = self.resolve_by_parameters(item)
            if part_pk:
                item.base_part_pk = part_pk
                item.resolution_status = "Resolved (Parameters)"
                self._fetch_part_metadata(item)
                return

            # Note: resolution_status might already be set to "Pending Manual Review (Complex)"
            if item.resolution_status == "Pending":
                item.resolution_status = "Not Found"

        except Exception as e:
            item.resolution_status = "Error"
            item.error_message = str(e)
