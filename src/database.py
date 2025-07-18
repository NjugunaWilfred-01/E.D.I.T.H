"""
EDITH Database Configuration

SQLAlchemy database setup with connection pooling, session management,
and migration support for the authentication system.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator

from src.config import config
from src.utils.logger import logger
from src.models import Base


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection and session factory"""
        try:
            # Create database engine with connection pooling
            self.engine = create_engine(
                config.database.connection_string,
                poolclass=QueuePool,
                pool_size=config.database.connection_pool_size,
                max_overflow=20,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections every hour
                echo=config.environment.value == "development"  # Log SQL in development
            )
            
            # Add connection event listeners
            event.listen(self.engine, "connect", self._on_connect)
            event.listen(self.engine, "checkout", self._on_checkout)
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _on_connect(self, dbapi_connection, connection_record):
        """Handle new database connections"""
        logger.debug("New database connection established")
        
        # Set connection-level settings for PostgreSQL
        if config.database.connection_string.startswith("postgresql"):
            with dbapi_connection.cursor() as cursor:
                # Set timezone to UTC
                cursor.execute("SET timezone TO 'UTC'")
                
                # Set statement timeout (30 seconds)
                cursor.execute("SET statement_timeout = '30s'")
                
                # Set lock timeout (10 seconds)
                cursor.execute("SET lock_timeout = '10s'")
    
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """Handle connection checkout from pool"""
        logger.debug("Database connection checked out from pool")
    
    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            with self.session_scope() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_connection_info(self) -> dict:
        """Get database connection information"""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency to get database session
    
    Yields:
        Database session
    """
    session = db_manager.get_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize database tables (for development/testing)"""
    try:
        db_manager.create_tables()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def reset_database():
    """Reset database (drop and recreate tables)"""
    try:
        logger.warning("Resetting database - all data will be lost!")
        db_manager.drop_tables()
        db_manager.create_tables()
        logger.info("Database reset completed")
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise


# Database health check function
async def check_database_health() -> dict:
    """
    Check database health and return status information
    
    Returns:
        Dictionary with health status and connection info
    """
    try:
        is_healthy = db_manager.health_check()
        connection_info = db_manager.get_connection_info()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "connection_info": connection_info,
            "database_url": config.database.host,
            "database_name": config.database.name
        }
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Migration support functions
def run_migrations():
    """Run database migrations using Alembic"""
    try:
        import alembic.config
        import alembic.command
        
        # Create Alembic configuration
        alembic_cfg = alembic.config.Config("alembic.ini")
        
        # Run migrations
        alembic.command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations completed successfully")
        
    except ImportError:
        logger.warning("Alembic not available, skipping migrations")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


def create_migration(message: str):
    """Create a new database migration"""
    try:
        import alembic.config
        import alembic.command
        
        # Create Alembic configuration
        alembic_cfg = alembic.config.Config("alembic.ini")
        
        # Create migration
        alembic.command.revision(alembic_cfg, message=message, autogenerate=True)
        
        logger.info(f"Migration created: {message}")
        
    except ImportError:
        logger.error("Alembic not available, cannot create migration")
        raise
    except Exception as e:
        logger.error(f"Migration creation failed: {e}")
        raise


# Database initialization for testing
def setup_test_database():
    """Setup database for testing"""
    if config.environment.value == "testing":
        try:
            # Create test database tables
            db_manager.create_tables()
            
            # Create test data if needed
            _create_test_data()
            
            logger.info("Test database setup completed")
            
        except Exception as e:
            logger.error(f"Test database setup failed: {e}")
            raise
    else:
        logger.warning("Test database setup called in non-testing environment")


def _create_test_data():
    """Create test data for development/testing"""
    from src.models import User, UserStatus
    from src.security.password import password_security
    
    try:
        with db_manager.session_scope() as session:
            # Check if test user already exists
            existing_user = session.query(User).filter(User.username == "testuser").first()
            
            if not existing_user:
                # Create test user
                password_hash, salt = password_security.hash_password("TestPassword123!")
                
                test_user = User(
                    username="testuser",
                    email="test@example.com",
                    password_hash=password_hash,
                    password_salt=salt,
                    status=UserStatus.ACTIVE,
                    is_verified=True
                )
                
                session.add(test_user)
                
                # Create admin user
                admin_password_hash, admin_salt = password_security.hash_password("AdminPassword123!")
                
                admin_user = User(
                    username="admin",
                    email="admin@example.com",
                    password_hash=admin_password_hash,
                    password_salt=admin_salt,
                    status=UserStatus.ACTIVE,
                    is_verified=True,
                    is_admin=True
                )
                
                session.add(admin_user)
                
                logger.info("Test data created successfully")
            else:
                logger.info("Test data already exists")
                
    except Exception as e:
        logger.error(f"Failed to create test data: {e}")
        raise
