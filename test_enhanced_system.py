#!/usr/bin/env python3
"""
Test script for the enhanced Pete Alonso tracking system
"""

import sys
import requests
import json
from datetime import datetime

def test_health_endpoint():
    """Test the health check endpoint"""
    try:
        print("🏥 Testing health endpoint...")
        response = requests.get("http://localhost:5000/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   Healthy: {data.get('healthy')}")
            print(f"   Processed at-bats: {data.get('processed_at_bats')}")
            print(f"   Last check: {data.get('last_check')}")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_stats_endpoint():
    """Test the stats API endpoint"""
    try:
        print("\n📊 Testing stats endpoint...")
        response = requests.get("http://localhost:5000/api/stats", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stats endpoint working")
            print(f"   Player: {data.get('player')}")
            print(f"   MLB ID: {data.get('mlb_id')}")
            print(f"   Processed at-bats: {data.get('processed_at_bats')}")
            
            season_stats = data.get('season_stats', {})
            if season_stats:
                print(f"   Season stats loaded: {len(season_stats)} fields")
                print(f"   Home runs: {season_stats.get('homeRuns', 'N/A')}")
                print(f"   Average: {season_stats.get('avg', 'N/A')}")
            else:
                print("   ⚠️ No season stats available")
            return True
        else:
            print(f"❌ Stats endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Stats endpoint error: {str(e)}")
        return False

def test_main_page():
    """Test the main web interface"""
    try:
        print("\n🌐 Testing main page...")
        response = requests.get("http://localhost:5000/", timeout=10)
        
        if response.status_code == 200:
            content = response.text
            if "Pete Alonso At-Bat Tracker" in content:
                print("✅ Main page loading correctly")
                if "Real-time monitoring" in content:
                    print("✅ Enhanced interface detected")
                return True
            else:
                print("❌ Main page content incorrect")
                return False
        else:
            print(f"❌ Main page failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Main page error: {str(e)}")
        return False

def test_mlb_api_connectivity():
    """Test connectivity to MLB API endpoints"""
    try:
        print("\n⚾ Testing MLB API connectivity...")
        
        # Test schedule endpoint
        schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
        params = {
            "sportId": 1,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        response = requests.get(schedule_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ MLB Schedule API accessible")
            
            if data.get('dates'):
                games_count = len(data['dates'][0].get('games', []))
                print(f"   Found {games_count} games today")
            
            return True
        else:
            print(f"❌ MLB API failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ MLB API error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting enhanced system tests...\n")
    
    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("Stats Endpoint", test_stats_endpoint),
        ("Main Page", test_main_page),
        ("MLB API", test_mlb_api_connectivity)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
    
    print(f"\n📋 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the system.")
        return 1

if __name__ == "__main__":
    exit(main()) 