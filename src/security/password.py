"""
EDITH Password Security Module

Military-grade password handling with advanced security features.
Implements bcrypt hashing, secure salt generation, and timing-attack resistance.
"""

import secrets
import string
import hashlib
import hmac
from typing import Tuple, Optional
from datetime import datetime, timedelta

from passlib.context import CryptContext
from passlib.hash import bcrypt

from src.config import config
from src.utils.logger import logger


class PasswordSecurity:
    """Advanced password security management"""
    
    def __init__(self):
        # Configure password context with bcrypt
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=config.security.password_hash_rounds
        )
        
        # Password strength requirements
        self.min_length = config.security.password_min_length
        self.require_special = config.security.password_require_special
        self.require_numbers = config.security.password_require_numbers
        self.require_uppercase = config.security.password_require_uppercase
    
    def hash_password(self, password: str) -> Tuple[str, str]:
        """
        Hash password with secure salt generation
        
        Args:
            password: Plain text password
            
        Returns:
            Tuple of (password_hash, salt)
        """
        # Generate cryptographically secure salt
        salt = self.generate_salt()
        
        # Create salted password
        salted_password = f"{salt}{password}"
        
        # Hash with bcrypt
        password_hash = self.pwd_context.hash(salted_password)
        
        logger.debug("Password hashed successfully")
        return password_hash, salt
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """
        Verify password against hash with timing-attack resistance
        
        Args:
            password: Plain text password to verify
            password_hash: Stored password hash
            salt: Stored salt
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            # Create salted password
            salted_password = f"{salt}{password}"
            
            # Verify with constant-time comparison
            is_valid = self.pwd_context.verify(salted_password, password_hash)
            
            if is_valid:
                logger.debug("Password verification successful")
            else:
                logger.warning("Password verification failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def generate_salt(self, length: int = 32) -> str:
        """
        Generate cryptographically secure salt
        
        Args:
            length: Salt length in bytes
            
        Returns:
            Base64 encoded salt string
        """
        salt_bytes = secrets.token_bytes(length)
        return salt_bytes.hex()
    
    def validate_password_strength(self, password: str) -> Tuple[bool, list]:
        """
        Validate password against security requirements
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Length check
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        
        # Character requirements
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.require_numbers and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        if self.require_special:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")
        
        # Common password checks
        if self.is_common_password(password):
            errors.append("Password is too common, please choose a more unique password")
        
        # Sequential character check
        if self.has_sequential_characters(password):
            errors.append("Password should not contain sequential characters")
        
        return len(errors) == 0, errors
    
    def is_common_password(self, password: str) -> bool:
        """
        Check if password is in common passwords list
        
        Args:
            password: Password to check
            
        Returns:
            True if password is common, False otherwise
        """
        # Common passwords list (in production, load from file)
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "1234567890", "password1",
            "123456789", "12345678", "12345", "1234567", "password12",
            "123123", "111111", "1234", "1234567890", "dragon",
            "master", "baseball", "football", "basketball", "superman"
        }
        
        return password.lower() in common_passwords
    
    def has_sequential_characters(self, password: str, max_sequence: int = 3) -> bool:
        """
        Check for sequential characters in password
        
        Args:
            password: Password to check
            max_sequence: Maximum allowed sequential characters
            
        Returns:
            True if password has sequential characters, False otherwise
        """
        # Check for ascending sequences
        for i in range(len(password) - max_sequence + 1):
            sequence = password[i:i + max_sequence]
            if self.is_ascending_sequence(sequence) or self.is_descending_sequence(sequence):
                return True
        
        return False
    
    def is_ascending_sequence(self, sequence: str) -> bool:
        """Check if string is ascending sequence"""
        return all(ord(sequence[i]) + 1 == ord(sequence[i + 1]) for i in range(len(sequence) - 1))
    
    def is_descending_sequence(self, sequence: str) -> bool:
        """Check if string is descending sequence"""
        return all(ord(sequence[i]) - 1 == ord(sequence[i + 1]) for i in range(len(sequence) - 1))
    
    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate cryptographically secure password
        
        Args:
            length: Password length
            
        Returns:
            Secure password string
        """
        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Ensure at least one character from each required set
        password = []
        password.append(secrets.choice(lowercase))
        
        if self.require_uppercase:
            password.append(secrets.choice(uppercase))
        
        if self.require_numbers:
            password.append(secrets.choice(digits))
        
        if self.require_special:
            password.append(secrets.choice(special))
        
        # Fill remaining length with random characters
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - len(password)):
            password.append(secrets.choice(all_chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)
    
    def check_password_age(self, password_changed_at: datetime, max_age_days: int = 90) -> bool:
        """
        Check if password is within acceptable age limit
        
        Args:
            password_changed_at: When password was last changed
            max_age_days: Maximum password age in days
            
        Returns:
            True if password is within age limit, False otherwise
        """
        if not password_changed_at:
            return False
        
        age = datetime.utcnow() - password_changed_at
        return age.days <= max_age_days
    
    def generate_password_reset_token(self, user_id: str) -> str:
        """
        Generate secure password reset token
        
        Args:
            user_id: User identifier
            
        Returns:
            Secure reset token
        """
        # Create token with timestamp and user ID
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"{user_id}:{timestamp}"
        
        # Create HMAC signature
        secret_key = config.security.jwt_secret_key.encode()
        signature = hmac.new(secret_key, data.encode(), hashlib.sha256).hexdigest()
        
        # Combine data and signature
        token = f"{data}:{signature}"
        
        # Encode to make it URL-safe
        import base64
        return base64.urlsafe_b64encode(token.encode()).decode()
    
    def verify_password_reset_token(self, token: str, user_id: str, max_age_hours: int = 24) -> bool:
        """
        Verify password reset token
        
        Args:
            token: Reset token to verify
            user_id: Expected user ID
            max_age_hours: Maximum token age in hours
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            import base64
            
            # Decode token
            decoded_token = base64.urlsafe_b64decode(token.encode()).decode()
            parts = decoded_token.split(':')
            
            if len(parts) != 3:
                return False
            
            token_user_id, timestamp_str, signature = parts
            
            # Verify user ID
            if token_user_id != user_id:
                return False
            
            # Verify timestamp
            timestamp = int(timestamp_str)
            token_age = datetime.utcnow().timestamp() - timestamp
            if token_age > (max_age_hours * 3600):
                return False
            
            # Verify signature
            data = f"{token_user_id}:{timestamp_str}"
            secret_key = config.security.jwt_secret_key.encode()
            expected_signature = hmac.new(secret_key, data.encode(), hashlib.sha256).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Password reset token verification error: {e}")
            return False


# Global password security instance
password_security = PasswordSecurity()
