import argparse
import logging
from photoserv.db import get_db, setup_db
from photoserv.auth import does_any_key_exist, create_key

# Set up logging to print to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def require_existing_key_or_exit():
    """Exit with instruction if no keys exist in the database."""
    with next(get_db()) as db:
        if not does_any_key_exist(db):
            logger.error(
                "No API keys exist. Use --create-admin-key to create one.")
            exit(1)


def create_admin_key():
    """Create and log a new admin key."""
    with next(get_db()) as db:
        admin_key = create_key(db, admin=True, name="Initial admin key.")
        logger.info(f"New admin key created: {admin_key}")


# --- CLI Setup ---
parser = argparse.ArgumentParser(
    description="Manage API Keys for the photoserv application."
)
parser.add_argument(
    "--create-admin-key",
    action="store_true",
    help="Create a new admin key and print it.",
)

args = parser.parse_args()

setup_db()

# Handle CLI commands
if args.create_admin_key:
    create_admin_key()
else:
    require_existing_key_or_exit()
