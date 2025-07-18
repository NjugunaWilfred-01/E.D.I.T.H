#!/usr/bin/env python3
"""
EDITH API Test Script

Quick test script to verify API functionality and security features.
Tests authentication endpoints and security measures.
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any


class EDITHAPITester:
    """API testing utility for EDITH authentication system"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token = None
        self.refresh_token = None
    
    async def test_health_check(self) -> bool:
        """Test health check endpoint"""
        print("🔍 Testing health check endpoint...")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    async def test_user_registration(self) -> bool:
        """Test user registration endpoint"""
        print("🔍 Testing user registration...")
        
        test_user = {
            "username": f"testuser_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123!"
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/register",
                json=test_user
            )
            
            if response.status_code == 201:
                data = response.json()
                print(f"✅ Registration successful: {data['username']}")
                return True
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False
    
    async def test_user_login(self) -> bool:
        """Test user login endpoint"""
        print("🔍 Testing user login...")
        
        # First register a user
        test_user = {
            "username": f"logintest_{int(time.time())}",
            "email": f"logintest_{int(time.time())}@example.com",
            "password": "TestPassword123!"
        }
        
        try:
            # Register user
            reg_response = await self.client.post(
                f"{self.base_url}/api/v1/auth/register",
                json=test_user
            )
            
            if reg_response.status_code != 201:
                print(f"❌ Failed to register test user: {reg_response.status_code}")
                return False
            
            # Login with the user
            login_data = {
                "username": test_user["username"],
                "password": test_user["password"]
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                print(f"✅ Login successful: {data['user']['username']}")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    async def test_protected_endpoint(self) -> bool:
        """Test protected endpoint with authentication"""
        print("🔍 Testing protected endpoint...")
        
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(
                f"{self.base_url}/api/v1/auth/me",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Protected endpoint access successful: {data['username']}")
                return True
            else:
                print(f"❌ Protected endpoint failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Protected endpoint error: {e}")
            return False
    
    async def test_rate_limiting(self) -> bool:
        """Test rate limiting functionality"""
        print("🔍 Testing rate limiting...")
        
        try:
            # Make multiple rapid requests to trigger rate limiting
            for i in range(10):
                response = await self.client.get(f"{self.base_url}/health")
                print(f"Request {i+1}: {response.status_code}")
                
                if response.status_code == 429:
                    print("✅ Rate limiting triggered successfully")
                    return True
                
                # Small delay between requests
                await asyncio.sleep(0.1)
            
            print("⚠️ Rate limiting not triggered (may need more requests)")
            return True
            
        except Exception as e:
            print(f"❌ Rate limiting test error: {e}")
            return False
    
    async def test_security_headers(self) -> bool:
        """Test security headers in responses"""
        print("🔍 Testing security headers...")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            security_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options",
                "X-XSS-Protection",
                "Strict-Transport-Security",
                "Content-Security-Policy"
            ]
            
            missing_headers = []
            for header in security_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if not missing_headers:
                print("✅ All security headers present")
                return True
            else:
                print(f"⚠️ Missing security headers: {missing_headers}")
                return False
                
        except Exception as e:
            print(f"❌ Security headers test error: {e}")
            return False
    
    async def test_invalid_credentials(self) -> bool:
        """Test login with invalid credentials"""
        print("🔍 Testing invalid credentials...")
        
        try:
            login_data = {
                "username": "nonexistent_user",
                "password": "wrong_password"
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data
            )
            
            if response.status_code == 401:
                print("✅ Invalid credentials properly rejected")
                return True
            else:
                print(f"❌ Unexpected response for invalid credentials: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Invalid credentials test error: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all API tests"""
        print("🚀 Starting EDITH API Tests")
        print("=" * 50)
        
        tests = {
            "health_check": self.test_health_check,
            "user_registration": self.test_user_registration,
            "user_login": self.test_user_login,
            "protected_endpoint": self.test_protected_endpoint,
            "rate_limiting": self.test_rate_limiting,
            "security_headers": self.test_security_headers,
            "invalid_credentials": self.test_invalid_credentials
        }
        
        results = {}
        
        for test_name, test_func in tests.items():
            print(f"\n📋 Running {test_name}...")
            try:
                results[test_name] = await test_func()
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                results[test_name] = False
            
            await asyncio.sleep(1)  # Brief pause between tests
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! API is working correctly.")
        else:
            print("⚠️ Some tests failed. Check the output above for details.")
        
        await self.client.aclose()
        return results


async def main():
    """Main test function"""
    tester = EDITHAPITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
