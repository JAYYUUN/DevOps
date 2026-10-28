"""Run explicitly before deploying the API; never run on every Pod startup."""
from sqlalchemy import text
from .config import get_settings
from .database import make_engine, Base
from .models.product import Product

def main():
    engine = make_engine(get_settings().database_url.get_secret_value())
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(40) PRIMARY KEY)'))
            version = conn.execute(text("SELECT version FROM schema_migrations WHERE version='001_products'")).first()
            if version is None:
                # Initial migration only. Future schema changes need new versioned scripts.
                Base.metadata.create_all(conn)
                conn.execute(text("INSERT INTO schema_migrations (version) VALUES ('001_products')"))
    finally:
        engine.dispose()

if __name__ == '__main__':
    main()
