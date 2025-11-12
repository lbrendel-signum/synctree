"""
Configuration management for SyncTree
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class DigikeyConfig:
    """Digikey API configuration"""
    client_id: str
    client_secret: str
    storage_path: Path
    sandbox: bool = False


@dataclass
class MouserConfig:
    """Mouser API configuration"""
    part_api_key: str


@dataclass
class InvenTreeConfig:
    """InvenTree API configuration"""
    server_url: str
    token: str


@dataclass
class Config:
    """Main configuration class"""
    digikey: Optional[DigikeyConfig] = None
    mouser: Optional[MouserConfig] = None
    inventree: Optional[InvenTreeConfig] = None

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        load_dotenv()
        
        # Digikey configuration
        digikey_config = None
        if os.getenv("DIGIKEY_CLIENT_ID") and os.getenv("DIGIKEY_CLIENT_SECRET"):
            storage_path = Path(os.getenv("DIGIKEY_STORAGE_PATH", Path.home() / ".synctree" / ".digikey"))
            storage_path.mkdir(parents=True, exist_ok=True)
            
            digikey_config = DigikeyConfig(
                client_id=os.getenv("DIGIKEY_CLIENT_ID"),
                client_secret=os.getenv("DIGIKEY_CLIENT_SECRET"),
                storage_path=storage_path,
                sandbox=os.getenv("DIGIKEY_CLIENT_SANDBOX", "False").lower() == "true"
            )
        
        # Mouser configuration
        mouser_config = None
        if os.getenv("MOUSER_PART_API_KEY"):
            mouser_config = MouserConfig(
                part_api_key=os.getenv("MOUSER_PART_API_KEY")
            )
        
        # InvenTree configuration
        inventree_config = None
        if os.getenv("INVENTREE_SERVER_URL") and os.getenv("INVENTREE_TOKEN"):
            inventree_config = InvenTreeConfig(
                server_url=os.getenv("INVENTREE_SERVER_URL"),
                token=os.getenv("INVENTREE_TOKEN")
            )
        
        return cls(
            digikey=digikey_config,
            mouser=mouser_config,
            inventree=inventree_config
        )
    
    def validate(self) -> None:
        """Validate that required configuration is present"""
        if not self.inventree:
            raise ValueError("InvenTree configuration is required (INVENTREE_SERVER_URL and INVENTREE_TOKEN)")
        
        if not self.digikey and not self.mouser:
            raise ValueError("At least one supplier API must be configured (Digikey or Mouser)")
