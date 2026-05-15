import re
from typing import Dict, Optional


class NamingConvention:
    @staticmethod
    def normalize_value(val: str) -> str:
        """Normalizes a technical value (e.g., '1 uF' -> '1uF', '10 kOhms' -> '10k')."""
        if not val:
            return ""

        # Remove parentheses: "0603 (1608 Metric)" -> "0603"
        val = val.split("(")[0].strip()

        # Remove spaces between number and unit: "1 uF" -> "1uF"
        val = re.sub(r"(\d+)\s+([a-zA-Z%]+)", r"\1\2", val)

        # Specific unit normalization
        val = val.replace("Ohms", "").replace("Ohm", "").strip()

        return val

    @classmethod
    def get_category_parameters(cls, parameters: Dict[str, str]) -> Dict[str, str]:
        """Maps API parameters to InvenTree parameter template names."""
        mapped = {}

        # Mapping logic for common passives
        if "Capacitance" in parameters:
            mapped["Capacitance"] = cls.normalize_value(parameters["Capacitance"])

        if "Resistance" in parameters:
            mapped["Resistance"] = cls.normalize_value(parameters["Resistance"])

        # SMD Size mapping
        size = cls.normalize_value(
            parameters.get("Case Code - in")
            or parameters.get("Package / Case")
            or parameters.get("Package")
            or ""
        )
        if size:
            mapped["SMD Size"] = size
            mapped["Package"] = size

        return mapped

    @classmethod
    def suggest_name(cls, parameters: Dict[str, str]) -> Optional[str]:
        """Suggests a part name based on technical parameters and naming conventions."""
        # Detect part type
        desc = parameters.get("Description", "").upper()

        # Capacitor Logic
        if "CAP" in desc:
            val = cls.normalize_value(parameters.get("Capacitance", ""))
            size = cls.normalize_value(
                parameters.get("Case Code - in")
                or parameters.get("Package / Case")
                or parameters.get("Package")
                or ""
            )
            if val and size:
                return f"C_{val}_{size}"

        # Resistor Logic
        if "RES" in desc:
            val = cls.normalize_value(parameters.get("Resistance", ""))
            size = cls.normalize_value(
                parameters.get("Case Code - in")
                or parameters.get("Package / Case")
                or parameters.get("Package")
                or ""
            )
            tol = cls.normalize_value(parameters.get("Tolerance", ""))

            if val and size:
                if tol:
                    return f"R_{val}_{size}_{tol}"
                return f"R_{val}_{size}"

        return None
