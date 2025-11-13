"""
InvenTree API client wrapper
"""

from datetime import datetime
import requests
import os
from pathlib import Path
import random
import string
from typing import Optional
from urllib.parse import quote

from inventree.api import InvenTreeAPI
from inventree.company import (
    Company,
    ManufacturerPart,
    ManufacturerPartParameter,
    SupplierPart,
    SupplierPriceBreak,
)
from inventree.part import Part, PartCategory, BomItem

from .config import InvenTreeConfig
from .suppliers import PartInfo


class ImageManager:
    cache_path: Path = Path(__file__).resolve().parent / "cache"

    @classmethod
    def get_image(cls, url: str) -> str:
        """
        Gets an image given an url
        returns a filepath
        """
        if not cls.cache_active():
            print("Cache not active creating...")
            cls._create_cache()

        path = cls._download_image(url)
        return path

    @classmethod
    def cache_active(cls):
        return os.path.exists(cls.cache_path)

    @classmethod
    def _create_cache(cls):
        try:
            print(f"Making cache at {cls.cache_path}")
            os.mkdir(cls.cache_path)
        except:
            print("Error making cache")

    @classmethod
    def clean_cache(cls):
        if cls.cache_active:
            for f in Path(cls.cache_path).glob("*"):
                f.unlink()

    def _filename_generator(size=6) -> str:
        return (
            "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(size)
            )
            + ".jpg"
        )

    @classmethod
    def _download_image(cls, url: str) -> str:
        print(f"Trying URL {url}")

        # escaped_url = quote(url, safe=":/")

        # Send an HTTP GET request with custom headers
        response = requests.get(url)

        if not response.status_code == 200:
            print(f"ERROR: Request code is {response.status_code}")
            return None

        filename = cls._filename_generator()

        filepath = cls.cache_path / filename
        with open(filepath, "wb") as handler:
            handler.write(response.content)

        return str(filepath)


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

        # Get or create manufacturer
        manufacturer = self.get_or_create_manufacturer(part_info.manufacturer_name)

        # Try to get/create category if provided
        category = None
        if part_info.category:
            category = self.get_or_create_category(part_info.category)

        # Search for existing part by name
        parts = Part.list(
            self.api, name=part_info.name, category=category.pk if category else None
        )

        if parts and (part_info.name in [p.name for p in parts]):
            part = next(p for p in parts if p.name == part_info.name)
            
            # Check if existing part needs an image
            if part_info.image_url:
                self.check_and_upload_part_image(part.pk, part_info.image_url)
            
            return part

        # Create new part
        part_data = {
            "name": part_info.name,
            "description": part_info.description,
            "component": True,
            "purchaseable": True,
            "active": True,
        }

        if category:
            part_data["category"] = category.pk

        part = Part.create(self.api, data=part_data)

        if part_info.image_url:
            image_path = ImageManager.get_image(part_info.image_url)
            if image_path:
                part.uploadImage(image_path)

        return part

    def create_manufacturer_part(
        self, part: Part, part_info: PartInfo
    ) -> ManufacturerPart:
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

    def create_supplier_part(
        self, part: Part, mpart: ManufacturerPart, part_info: PartInfo
    ) -> SupplierPart:
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
            "active": part_info.is_active,
            "part": part.pk,
            "supplier": supplier.pk,
            "SKU": part_info.supplier_part_number,
            "manufacturer_part": mpart.pk,
            "MPN": part_info.manufacturer_part_number,
            "description": part_info.description,
            "link": part_info.url or "",
            "note": f"Synced from {part_info.supplier_name}",
        }

        # Add packaging info if available
        if part_info.packaging:
            supplier_part_data["packaging"] = part_info.packaging

        spart = SupplierPart.create(self.api, data=supplier_part_data)

        if part_info.pricing:
            for qty, price in part_info.pricing.items():
                SupplierPriceBreak.create(
                    self.api,
                    data={
                        "part": spart.pk,
                        "quantity": qty,
                        "price": price,
                        "supplier": supplier.pk,
                        "updated": datetime.now().isoformat(),
                    },
                )

        return spart

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
        mpart = self.create_manufacturer_part(part, part_info)

        # Create supplier part link
        supplier_part = self.create_supplier_part(part, mpart, part_info)

        return part, supplier_part

    def create_assembly_part(self, part_number: str) -> Optional[dict]:
        """
        Create an assembly part in InvenTree

        Args:
            part_number: Part number for the assembly

        Returns:
            Dictionary with part info or None if failed
        """
        try:
            # Check if part already exists
            existing_parts = Part.list(self.api, IPN=part_number)
            if existing_parts:
                part = existing_parts[0]
                return {
                    "inventree_part_id": part.pk,
                    "name": part.name,
                    "description": part.description,
                    "exists": True,
                }

            # Create new assembly part
            part_data = {
                "name": part_number,
                "IPN": part_number,
                "description": f"Assembly: {part_number}",
                "component": False,
                "assembly": True,
                "purchaseable": False,
                "active": True,
                "revision": "R100",
            }

            part = Part.create(self.api, data=part_data)

            return {
                "inventree_part_id": part.pk,
                "name": part.name,
                "description": part.description,
                "exists": False,
            }
        except Exception as e:
            print(f"Error creating assembly part: {e}")
            return None

    def add_bom_item(
        self,
        assembly_part_id: int,
        sub_part_id: int,
        quantity: float,
        reference: str = "",
    ) -> Optional[dict]:
        """
        Add a BOM item to an assembly

        Args:
            assembly_part_id: ID of the assembly part
            sub_part_id: ID of the sub-part to add
            quantity: Quantity required
            reference: Reference designators (optional)

        Returns:
            Dictionary with BOM item info or None if failed
        """
        try:
            # Check if BOM item already exists
            existing = BomItem.list(
                self.api, part=assembly_part_id, sub_part=sub_part_id
            )

            if existing and any(True for item in existing if item.part == assembly_part_id and item.sub_part == sub_part_id):
                # Update existing BOM item
                bom_item = next(
                    item
                    for item in existing
                    if item.part == assembly_part_id and item.sub_part == sub_part_id
                )
                # Optionally update quantity or reference
                return {"bom_item_id": bom_item.pk, "exists": True}

            # Create new BOM item
            bom_data = {
                "part": assembly_part_id,
                "sub_part": sub_part_id,
                "quantity": quantity,
            }

            if reference:
                bom_data["reference"] = reference

            bom_item = BomItem.create(self.api, data=bom_data)

            return {"bom_item_id": bom_item.pk, "exists": False}
        except Exception as e:
            print(f"Error adding BOM item: {e}")
            return None

    def get_all_supplier_parts(self, supplier_name: Optional[str] = None) -> list:
        """
        Get all supplier parts from InvenTree

        Args:
            supplier_name: Filter by supplier name (None = all suppliers)

        Returns:
            List of supplier part dictionaries
        """
        try:
            # List all supplier parts
            if supplier_name:
                # Get supplier company first
                suppliers = Company.list(self.api, name=supplier_name, is_supplier=True)
                if suppliers:
                    supplier_id = suppliers[0].pk
                    supplier_parts = SupplierPart.list(self.api, supplier=supplier_id)
                else:
                    return []
            else:
                supplier_parts = SupplierPart.list(self.api)

            # Convert to dictionaries with all data
            result = []
            for sp in supplier_parts:
                # Get supplier details
                supplier_data = sp._data if hasattr(sp, '_data') else {}
                result.append(supplier_data)

            return result
        except Exception as e:
            print(f"Error getting supplier parts: {e}")
            return []

    def update_supplier_part(self, supplier_part_id: int, part_info: PartInfo) -> bool:
        """
        Update a supplier part in InvenTree with new data from supplier

        Args:
            supplier_part_id: ID of the supplier part to update
            part_info: New part information from supplier

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get the supplier part
            supplier_part = SupplierPart(self.api, pk=supplier_part_id)

            # Update active status
            supplier_part.save(data={
                'active': part_info.is_active
            })

            # Update pricing if available
            if part_info.pricing:
                # Delete existing price breaks
                existing_prices = SupplierPriceBreak.list(
                    self.api,
                    part=supplier_part_id
                )
                for price in existing_prices:
                    price.delete()

                # Add new price breaks
                supplier = Company.list(
                    self.api,
                    name=part_info.supplier_name,
                    is_supplier=True
                )[0]

                for qty, price in part_info.pricing.items():
                    SupplierPriceBreak.create(
                        self.api,
                        data={
                            "part": supplier_part_id,
                            "quantity": qty,
                            "price": price,
                            "supplier": supplier.pk,
                            "updated": datetime.now().isoformat(),
                        },
                    )

            return True
        except Exception as e:
            print(f"Error updating supplier part: {e}")
            return False

    def check_and_upload_part_image(self, part_id: int, image_url: str) -> bool:
        """
        Check if a part has an image, and if not, upload from the given URL
        
        Args:
            part_id: ID of the part to check
            image_url: URL of the image to upload if missing
            
        Returns:
            True if image was uploaded, False otherwise
        """
        try:
            # Get the part
            part = Part(self.api, pk=part_id)
            
            # Check if part already has an image
            # The image field in InvenTree is typically stored as 'image'
            if hasattr(part, '_data') and part._data.get('image'):
                # Part already has an image
                return False
            
            # No image, so download and upload it
            if image_url:
                image_path = ImageManager.get_image(image_url)
                if image_path:
                    part.uploadImage(image_path)
                    return True
            
            return False
        except Exception as e:
            print(f"Error checking/uploading part image: {e}")
            return False
