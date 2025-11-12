"""
Supplier API client interfaces
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import digikey
from digikey.v4.productinformation import KeywordRequest
from mouser.api import MouserPartSearchRequest

from .config import DigikeyConfig, MouserConfig


@dataclass
class PartInfo:
    """Standardized part information from suppliers"""
    manufacturer_name: str
    manufacturer_part_number: str
    supplier_name: str
    supplier_part_number: str
    description: str
    datasheet_url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    packaging: Optional[str] = None
    stock: Optional[int] = None
    pricing: Optional[dict] = None


class SupplierClient(ABC):
    """Abstract base class for supplier API clients"""
    
    @abstractmethod
    def get_part_info(self, part_number: str) -> Optional[PartInfo]:
        """
        Get part information from supplier API
        
        Args:
            part_number: Part number to search for (can be supplier PN or manufacturer PN)
            
        Returns:
            PartInfo object if found, None otherwise
        """
        pass


class DigikeyClient(SupplierClient):
    """Digikey API client"""
    
    def __init__(self, config: DigikeyConfig):
        self.config = config
        # Set environment variables for digikey library
        os.environ["DIGIKEY_CLIENT_ID"] = config.client_id
        os.environ["DIGIKEY_CLIENT_SECRET"] = config.client_secret
        os.environ["DIGIKEY_STORAGE_PATH"] = str(config.storage_path)
        os.environ["DIGIKEY_CLIENT_SANDBOX"] = str(config.sandbox)
    
    def get_part_info(self, part_number: str) -> Optional[PartInfo]:
        """Get part information from Digikey"""
        try:
            # Try direct product details first (works best with Digikey part numbers)
            part = digikey.product_details(part_number)
            
            if part and hasattr(part, 'digi_key_part_number'):
                return self._convert_to_part_info(part)
            
        except Exception as e:
            # If direct lookup fails, try keyword search
            try:
                search_request = KeywordRequest(keywords=part_number, limit=1, offset=0)
                result = digikey.keyword_search(body=search_request)
                
                if result and hasattr(result, 'products') and len(result.products) > 0:
                    # Get detailed info for the first result
                    first_product = result.products[0]
                    if hasattr(first_product, 'digi_key_part_number'):
                        part = digikey.product_details(first_product.digi_key_part_number)
                        return self._convert_to_part_info(part)
            except Exception:
                pass
        
        return None
    
    def _convert_to_part_info(self, part) -> PartInfo:
        """Convert Digikey API response to PartInfo"""
        # Extract pricing information
        pricing = {}
        if hasattr(part, 'standard_pricing') and part.standard_pricing:
            for price in part.standard_pricing:
                if hasattr(price, 'break_quantity') and hasattr(price, 'unit_price'):
                    pricing[price.break_quantity] = price.unit_price
        
        return PartInfo(
            manufacturer_name=part.manufacturer.value if hasattr(part, 'manufacturer') else "",
            manufacturer_part_number=part.manufacturer_part_number if hasattr(part, 'manufacturer_part_number') else "",
            supplier_name="Digikey",
            supplier_part_number=part.digi_key_part_number if hasattr(part, 'digi_key_part_number') else "",
            description=part.product_description if hasattr(part, 'product_description') else "",
            datasheet_url=part.primary_datasheet if hasattr(part, 'primary_datasheet') else None,
            image_url=part.primary_photo if hasattr(part, 'primary_photo') else None,
            category=part.category.value if hasattr(part, 'category') else None,
            packaging=part.packaging.value if hasattr(part, 'packaging') else None,
            stock=part.quantity_available if hasattr(part, 'quantity_available') else None,
            pricing=pricing if pricing else None
        )


class MouserClient(SupplierClient):
    """Mouser API client"""
    
    def __init__(self, config: MouserConfig):
        self.config = config
        # Set environment variable for mouser library
        os.environ["MOUSER_PART_API_KEY"] = config.part_api_key
    
    def get_part_info(self, part_number: str) -> Optional[PartInfo]:
        """Get part information from Mouser"""
        try:
            request = MouserPartSearchRequest()
            result = request.part_search(part_number)
            
            if result and hasattr(result, 'Parts') and len(result.Parts) > 0:
                part = result.Parts[0]
                return self._convert_to_part_info(part)
                
        except Exception:
            pass
        
        return None
    
    def _convert_to_part_info(self, part) -> PartInfo:
        """Convert Mouser API response to PartInfo"""
        # Extract pricing information
        pricing = {}
        if hasattr(part, 'PriceBreaks') and part.PriceBreaks:
            for price_break in part.PriceBreaks:
                if hasattr(price_break, 'Quantity') and hasattr(price_break, 'Price'):
                    # Remove currency symbols and convert to float
                    price_str = price_break.Price.replace('$', '').replace(',', '')
                    try:
                        pricing[int(price_break.Quantity)] = float(price_str)
                    except (ValueError, AttributeError):
                        pass
        
        return PartInfo(
            manufacturer_name=part.Manufacturer if hasattr(part, 'Manufacturer') else "",
            manufacturer_part_number=part.ManufacturerPartNumber if hasattr(part, 'ManufacturerPartNumber') else "",
            supplier_name="Mouser",
            supplier_part_number=part.MouserPartNumber if hasattr(part, 'MouserPartNumber') else "",
            description=part.Description if hasattr(part, 'Description') else "",
            datasheet_url=part.DataSheetUrl if hasattr(part, 'DataSheetUrl') else None,
            image_url=part.ImagePath if hasattr(part, 'ImagePath') else None,
            category=part.Category if hasattr(part, 'Category') else None,
            packaging=part.ProductDetailUrl if hasattr(part, 'ProductDetailUrl') else None,
            stock=int(part.AvailabilityInStock) if hasattr(part, 'AvailabilityInStock') else None,
            pricing=pricing if pricing else None
        )
