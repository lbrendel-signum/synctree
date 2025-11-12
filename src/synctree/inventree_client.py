"""
InvenTree API client wrapper
"""

from typing import Optional

from inventree.api import InvenTreeAPI
from inventree.company import Company, SupplierPart, ManufacturerPart, ManufacturerPartParameter
from inventree.part import Part, PartCategory

from .config import InvenTreeConfig
from .suppliers import PartInfo


class InvenTreeClient:
    """Client for interacting with InvenTree API"""

    def __init__(self, config: InvenTreeConfig):
        self.config = config
        self.api = InvenTreeAPI(
            host=config.server_url,
            token=config.token,
            use_token_auth=True,
            strict=False,
        )

    def get_or_create_manufacturer(self, name: str) -> Company:
        """Get or create a manufacturer company"""
        # Search for existing manufacturer
        manufacturers = Company.list(self.api, name=name, is_manufacturer=True)

        if manufacturers:
            return manufacturers[0]

        # Create new manufacturer
        return Company.create(
            self.api,
            data={
                "name": name,
                "is_manufacturer": True,
                "is_supplier": False,
                "is_customer": False,
            },
        )

    def get_or_create_supplier(self, name: str) -> Company:
        """Get or create a supplier company"""
        # Search for existing supplier
        suppliers = Company.list(self.api, name=name, is_supplier=True)

        if suppliers:
            return suppliers[0]

        # Create new supplier
        return Company.create(
            self.api,
            data={
                "name": name,
                "description": f"Supplier: {name}",
                "is_manufacturer": False,
                "is_supplier": True,
                "is_customer": False,
            },
        )

    def get_or_create_category(
        self, name: str, parent: Optional[int] = None
    ) -> PartCategory:
        """Get or create a part category"""
        # Search for existing category
        categories = PartCategory.list(self.api, name=name, parent=parent)

        if categories:
            return categories[0]

        # Create new category
        data = {
            "name": name,
        }
        if parent:
            data["parent"] = parent

        return PartCategory.create(self.api, data=data)

    def get_or_create_part(self, part_info: PartInfo) -> Part:
        """Get or create a part in InvenTree"""
        # Search for existing part by name
        parts = Part.list(self.api, name=part_info.name)

        if parts:
            return parts[0]

        # Get or create manufacturer
        manufacturer = self.get_or_create_manufacturer(part_info.manufacturer_name)

        # Try to get/create category if provided
        category = None
        if part_info.category:
            category = self.get_or_create_category(part_info.category)

        # Create new part
        part_data = {
            "name": part_info.name,
            "description": part_info.description,
            "component": True,
            "purchaseable": True,
            "active": True,
            # TODO: Add parameters
        }

        if category:
            part_data["category"] = category.pk

        part = Part.create(self.api, data=part_data)


        return part

    def create_manufacturer_part(self, part: Part, part_info: PartInfo) -> ManufacturerPart:
        """Create a manufacturer part link"""
        # Get or create manufacturer
        manufacturer = self.get_or_create_manufacturer(part_info.manufacturer_name)

        # Check if manufacturer part already exists
        existing = ManufacturerPart.list(
            self.api,
            manufacturer=manufacturer.pk,
            MPN=part_info.manufacturer_part_number,
        )

        if existing:
            return existing[0]

        # Create manufacturer part
        manufacturer_part_data = {
            "part": int(part.pk),
            "manufacturer": int(manufacturer.pk),
            "MPN": part_info.manufacturer_part_number,
            "description": part_info.description,
            "link": part_info.datasheet_url or "",
            "note": f"Synced from {part_info.supplier_name}",
        }

        mpart = ManufacturerPart.create(self.api, data=manufacturer_part_data)

        if part_info.parameters:
            for key, value in part_info.parameters.items():
                ManufacturerPartParameter.create(
                    self.api,
                    data={
                        "manufacturer_part": mpart.pk,
                        "name": key,
                        "value": value,
                    },
                )

        return mpart

    def create_supplier_part(self, part: Part, part_info: PartInfo) -> SupplierPart:
        """Create a supplier part link"""
        # Get or create supplier
        supplier = self.get_or_create_supplier(part_info.supplier_name)

        # Check if supplier part already exists
        existing = SupplierPart.list(
            self.api,
            part=part.pk,
            supplier=supplier.pk,
            SKU=part_info.supplier_part_number,
        )

        if existing:
            return existing[0]

        # Create supplier part
        supplier_part_data = {
            "part": part.pk,
            "supplier": supplier.pk,
            "SKU": part_info.supplier_part_number,
            "description": part_info.description,
            "link": part_info.datasheet_url or "",
            "note": f"Synced from {part_info.supplier_name}",
        }

        # Add packaging info if available
        if part_info.packaging:
            supplier_part_data["packaging"] = part_info.packaging

        return SupplierPart.create(self.api, data=supplier_part_data)

    def sync_part(self, part_info: PartInfo) -> tuple[Part, SupplierPart]:
        """
        Sync a part to InvenTree

        Creates/updates:
        - Manufacturer company
        - Supplier company
        - Part with manufacturer info
        - Supplier part link

        Returns:
            Tuple of (Part, SupplierPart)
        """
        # Get or create the part
        part = self.get_or_create_part(part_info)

        # Get or create manufacturer part link
        self.create_manufacturer_part(part, part_info)

        # Create supplier part link
        supplier_part = self.create_supplier_part(part, part_info)

        return part, supplier_part
