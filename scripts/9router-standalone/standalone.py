"""9Router Standalone Manager (CRUD API version)

Estrutura:

    config.json
        ├── instance
        └── defaults
             ├── models
             ├── combos
             └── publish

Operações:

    python standalone.py list
    python standalone.py test

    python standalone.py sync
    python standalone.py sync --dry-run

    python standalone.py fetch

    python standalone.py backup
    python standalone.py backup --output standalone-backup.json

    python standalone.py clean
    python standalone.py clean --dry-run

    python standalone.py watch
    python standalone.py watch --interval 180 --fetch-interval 600

Arquitetura:

    Standalone
        ├── proxyPools (Tor)
        ├── combos (modelos do defaults)
        └── customModels (modelos upstream)

Versão: 1.0 (Modular — src/server_standalone/)
"""

import sys
from pathlib import Path

# Adicionar src/ ao path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from server_standalone.__main__ import main

if __name__ == "__main__":
    main()