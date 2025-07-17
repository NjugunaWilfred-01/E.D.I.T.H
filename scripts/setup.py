#!/usr/bin/env python3
"""
EDITH Authentication System Setup Script

Automated setup for development environment with security best practices.
"""

import os
import sys
import subprocess
import secrets
import string
from pathlib import Path


class EDITHSetup:
    """Setup automation for EDITH authentication system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.env_file = self.project_root / ".env"
        self.env_example = self.project_root / ".env.example"
    
    def run_setup(self):
        """Execute complete setup process"""
        print("EDITH Authentication System Setup")
        print("=" * 50)
        
        try:
            self.check_python_version()
            self.create_virtual_environment()
            self.install_dependencies()
            self.setup_environment_file()
            self.create_directories()
            self.setup_git_hooks()
            self.run_security_checks()
            
            print("\nSetup completed successfully!")
            print("\nNext steps:")
            print("1. Activate virtual environment: source venv/bin/activate")
            print("2. Update .env file with your configuration")
            print("3. Start development: python -m src.main")
            
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            sys.exit(1)
    
    def check_python_version(self):
        """Verify Python version compatibility"""
        print("Checking Python version...")
        
        if sys.version_info < (3, 9):
            raise RuntimeError("Python 3.9 or higher is required")
        
        print(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    def create_virtual_environment(self):
        """Create and setup virtual environment"""
        print("Creating virtual environment...")
        
        venv_path = self.project_root / "venv"
        
        if venv_path.exists():
            print("Virtual environment already exists")
            return
        
        subprocess.run([
            sys.executable, "-m", "venv", str(venv_path)
        ], check=True)
        
        print("Virtual environment created")
    
    def install_dependencies(self):
        """Install Python dependencies"""
        print("Installing dependencies...")
        
        venv_python = self.project_root / "venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = self.project_root / "venv" / "Scripts" / "python.exe"
        
        # Upgrade pip
        subprocess.run([
            str(venv_python), "-m", "pip", "install", "--upgrade", "pip"
        ], check=True)
        
        # Install requirements
        subprocess.run([
            str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        
        print("Dependencies installed")
    
    def setup_environment_file(self):
        """Create .env file from template with secure defaults"""
        print("Setting up environment configuration...")
        
        if self.env_file.exists():
            print(".env file already exists")
            return
        
        # Read template
        with open(self.env_example, 'r') as f:
            env_content = f.read()
        
        # Generate secure JWT secret
        jwt_secret = self.generate_secure_key(64)
        env_content = env_content.replace(
            "your-super-secret-jwt-key-change-this-in-production",
            jwt_secret
        )
        
        # Generate secure database password
        db_password = self.generate_secure_key(32)
        env_content = env_content.replace(
            "change_this_password",
            db_password
        )
        
        # Write .env file
        with open(self.env_file, 'w') as f:
            f.write(env_content)
        
        # Set secure permissions
        os.chmod(self.env_file, 0o600)
        
        print("Environment file created with secure defaults")
    
    def generate_secure_key(self, length: int) -> str:
        """Generate cryptographically secure random key"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def create_directories(self):
        """Create necessary directories"""
        print("Creating project directories...")
        
        directories = [
            "logs",
            "data",
            "backups",
            "uploads",
            "static",
            "templates"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            
            # Create .gitkeep for empty directories
            gitkeep = dir_path / ".gitkeep"
            if not any(dir_path.iterdir()):
                gitkeep.touch()
        
        print("Directories created")
    
    def setup_git_hooks(self):
        """Setup Git hooks for code quality"""
        print("Setting up Git hooks...")
        
        git_hooks_dir = self.project_root / ".git" / "hooks"
        if not git_hooks_dir.exists():
            print("Not a Git repository, skipping hooks setup")
            return
        
        # Pre-commit hook
        pre_commit_hook = git_hooks_dir / "pre-commit"
        pre_commit_content = """#!/bin/bash
# EDITH Pre-commit Hook

echo "Running pre-commit checks..."

# Run code formatting
python -m black src/ tests/ --check
if [ $? -ne 0 ]; then
    echo "Code formatting check failed. Run: python -m black src/ tests/"
    exit 1
fi

# Run linting
python -m flake8 src/ tests/
if [ $? -ne 0 ]; then
    echo "Linting failed"
    exit 1
fi

# Run type checking
python -m mypy src/
if [ $? -ne 0 ]; then
    echo "Type checking failed"
    exit 1
fi

# Run security checks
python -m bandit -r src/
if [ $? -ne 0 ]; then
    echo "Security check failed"
    exit 1
fi

echo "All pre-commit checks passed"
"""
        
        with open(pre_commit_hook, 'w') as f:
            f.write(pre_commit_content)
        
        os.chmod(pre_commit_hook, 0o755)
        
        print("Git hooks configured")
    
    def run_security_checks(self):
        """Run initial security checks"""
        print("Running security checks...")
        
        try:
            # Check for common security issues
            subprocess.run([
                "python", "-m", "bandit", "-r", "src/", "-f", "txt"
            ], check=True, capture_output=True)
            
            # Check for known vulnerabilities
            subprocess.run([
                "python", "-m", "safety", "check"
            ], check=True, capture_output=True)
            
            print("Security checks passed")
            
        except subprocess.CalledProcessError as e:
            print(f"Security warnings detected: {e}")
            print("Review the output and address any critical issues")


if __name__ == "__main__":
    setup = EDITHSetup()
    setup.run_setup()
