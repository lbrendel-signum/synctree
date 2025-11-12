# SyncTree

Syncing supplier part information to InvenTree

## Overview

SyncTree is a Python tool that synchronizes part information from electronic component supplier APIs (Digikey and Mouser) to your InvenTree instance. It automatically creates or updates:

- Manufacturer companies
- Supplier companies  
- Parts with manufacturer information
- Supplier part links

This makes it easy to add parts to your InvenTree database by simply providing a part number.

## Features

- ✅ Support for multiple suppliers (Digikey, Mouser)
- ✅ Automatic manufacturer and supplier company creation
- ✅ Part synchronization with full metadata
- ✅ CLI interface for easy part syncing
- ✅ Built with uv for fast, reproducible builds
- ✅ Uses custom digikey-api and mouser-api packages

## Requirements

- Python 3.12+
- uv package manager
- InvenTree instance with API access
- Digikey and/or Mouser API credentials

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/lbrendel-signum/synctree.git
cd synctree

# Install uv if you haven't already
pip install uv

# Sync dependencies and install
uv sync
```

### Using pip

```bash
pip install git+https://github.com/lbrendel-signum/synctree.git
```

## Configuration

SyncTree uses environment variables for configuration. Create a `.env` file in your working directory:

```bash
# InvenTree Configuration (Required)
INVENTREE_SERVER_URL=https://your-inventree-instance.com
INVENTREE_TOKEN=your-inventree-api-token

# Digikey Configuration (Optional - but at least one supplier required)
DIGIKEY_CLIENT_ID=your-digikey-client-id
DIGIKEY_CLIENT_SECRET=your-digikey-client-secret
DIGIKEY_STORAGE_PATH=/path/to/cache/dir  # Optional, defaults to ~/.synctree/.digikey
DIGIKEY_CLIENT_SANDBOX=False  # Optional, defaults to False

# Mouser Configuration (Optional - but at least one supplier required)
MOUSER_PART_API_KEY=your-mouser-part-api-key
```

### Getting API Credentials

#### InvenTree
1. Log into your InvenTree instance
2. Go to Settings → User Settings → API Tokens
3. Create a new token with appropriate permissions

#### Digikey
1. Register an app at [Digi-Key API Portal](https://developer.digikey.com/get_started)
2. Set OAuth Callback to `https://localhost:8139/digikey_callback`
3. Note your Client ID and Client Secret
4. Use Production App credentials for real data (Sandbox may return dummy data)

#### Mouser
1. Request API keys at [Mouser API Hub](https://www.mouser.com/api-hub/)
2. You'll receive a Part Search API key
3. Use the Part Search API key as `MOUSER_PART_API_KEY`

## Usage

### Command Line Interface

Check configuration status:
```bash
synctree config
```

Sync a part by part number:
```bash
# Will search all configured suppliers
synctree sync 296-6501-1-ND

# Specify a particular supplier
synctree sync CRCW080510K0FKEA --supplier digikey

# Verbose output with more details
synctree sync STM32F103C8T6 --verbose
```

### Development Usage

If you're developing and using uv:

```bash
# Activate the virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Run synctree
synctree sync 296-6501-1-ND
```

### Python API

You can also use SyncTree programmatically:

```python
from synctree.config import Config
from synctree.sync_service import SyncService

# Load configuration from environment
config = Config.from_env()

# Create sync service
service = SyncService(config)

# Sync a part
result = service.sync_part("296-6501-1-ND")

if result:
    print(f"Synced: {result['manufacturer_part_number']}")
    print(f"InvenTree Part ID: {result['inventree_part_id']}")
else:
    print("Part not found")
```

## How It Works

When you provide a part number, SyncTree:

1. **Searches Supplier APIs**: Queries configured supplier APIs (Digikey/Mouser) for the part
2. **Extracts Information**: Gets manufacturer name, MPN, description, datasheet, etc.
3. **Creates/Updates Manufacturer**: Ensures the manufacturer company exists in InvenTree
4. **Creates/Updates Supplier**: Ensures the supplier company exists in InvenTree
5. **Creates/Updates Part**: Creates the part with manufacturer information
6. **Links Supplier Part**: Creates the supplier part relationship with SKU and pricing

All operations are idempotent - running the same sync multiple times is safe.

## Project Structure

```
synctree/
├── src/
│   └── synctree/
│       ├── __init__.py          # Package initialization
│       ├── cli.py               # Command-line interface
│       ├── config.py            # Configuration management
│       ├── suppliers.py         # Supplier API clients (Digikey, Mouser)
│       ├── inventree_client.py  # InvenTree API wrapper
│       └── sync_service.py      # Main sync service logic
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

## Dependencies

- `inventree` - InvenTree Python API client
- `digikey-api` - Custom Digikey API client (from lbrendel-signum/digikey-api)
- `mouser` - Custom Mouser API client (from lbrendel-signum/mouser-api)
- `python-dotenv` - Environment variable management
- `typer` - CLI framework
- `requests` - HTTP library

## Troubleshooting

### "Configuration error: InvenTree configuration is required"
Make sure you've set `INVENTREE_SERVER_URL` and `INVENTREE_TOKEN` environment variables.

### "Configuration error: At least one supplier API must be configured"
Set up at least one supplier (Digikey or Mouser) with the appropriate API credentials.

### Digikey OAuth Flow
The first time you use Digikey, a browser window will open for OAuth authentication. Follow the prompts to authorize the application. The tokens will be cached in the storage directory.

### Part Not Found
- Verify the part number is correct
- Try searching with the manufacturer part number instead of supplier SKU
- Check that your API credentials are valid and not sandbox credentials

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See LICENSE file for details.

## Credits

Built with:
- Custom [digikey-api](https://github.com/lbrendel-signum/digikey-api) package
- Custom [mouser-api](https://github.com/lbrendel-signum/mouser-api) package
- [InvenTree](https://inventree.org/) inventory management system

