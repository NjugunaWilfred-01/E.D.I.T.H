#!/usr/bin/env python3
"""
EDITH API Server Startup Script

Development server startup with database initialization and configuration validation.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config
from src.utils.logger import logger
from src.database import init_database, setup_test_database


def validate_environment():
    """Validate environment configuration"""
    print("🔍 Validating environment configuration...")
    
    # Check required environment variables
    required_vars = [
        "JWT_SECRET_KEY",
        "DB_HOST",
        "DB_NAME",
        "DB_USERNAME",
        "DB_PASSWORD"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please check your .env file")
        return False
    
    print("✅ Environment configuration valid")
    return True


def setup_database():
    """Initialize database"""
    print("🗄️ Setting up database...")
    
    try:
        if config.environment.value == "testing":
            setup_test_database()
        else:
            init_database()
        
        print("✅ Database setup completed")
        return True
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False


def start_server():
    """Start the FastAPI server"""
    print("🚀 Starting EDITH Authentication API Server...")
    print(f"Environment: {config.environment.value}")
    print(f"Host: 0.0.0.0")
    print(f"Port: 8000")
    print(f"Docs: http://localhost:8000/docs")
    print("=" * 50)
    
    # Server configuration based on environment
    server_config = {
        "app": "src.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "log_level": "info",
        "access_log": True,
    }
    
    if config.environment.value == "development":
        server_config.update({
            "reload": True,
            "reload_dirs": [str(project_root / "src")],
        })
    
    # Start server
    uvicorn.run(**server_config)


def main():
    """Main startup function"""
    print("🔐 EDITH Authentication System")
    print("Elite-Grade Artificial Intelligence Authentication API")
    print("=" * 50)
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Start server
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n🔒 Server shutdown requested")
        logger.info("EDITH Authentication API server stopped")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        logger.error(f"Server startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
