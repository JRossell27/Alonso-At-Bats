#!/usr/bin/env python3
"""
Debug script to test Baseball Savant API directly
"""

import requests
from datetime import datetime, timedelta

def test_baseball_savant_api():
    """Test various Baseball Savant API endpoints"""
    print("🔍 Testing Baseball Savant API Endpoints")
    print("=" * 60)
    
    # Test basic connectivity
    base_url = "https://baseballsavant.mlb.com"
    
    # Try the statcast search CSV endpoint with broader parameters
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Testing with date: {yesterday}")
    
    # Test 1: Basic statcast search for any data from yesterday
    params = {
        'all': 'true',
        'hfPT': '',
        'hfAB': '',
        'hfBBT': '',
        'hfPR': '',
        'hfZ': '',
        'stadium': '',
        'hfBBL': '',
        'hfNewZones': '',
        'hfGT': 'R|',  # Regular season
        'hfC': '',
        'hfSea': '2025|',  # Current season
        'hfSit': '',
        'player_type': 'batter',
        'hfOuts': '',
        'opponent': '',
        'pitcher_throws': '',
        'batter_stands': '',
        'hfSA': '',
        'game_date_gt': yesterday,
        'game_date_lt': yesterday,
        'hfInfield': '',
        'team': '',
        'position': '',
        'hfOutfield': '',
        'hfRO': '',
        'home_road': '',
        'hfFlag': '',
        'hfPull': '',
        'metric_1': '',
        'hfInn': '',
        'min_pitches': '0',
        'min_results': '0',
        'group_by': 'name',
        'sort_col': 'pitches',
        'player_event_sort': 'h_launch_speed',
        'sort_order': 'desc',
        'min_pas': '0',
        'type': 'details',
    }
    
    print("\n1. Testing general Statcast data for yesterday...")
    try:
        url = f"{base_url}/statcast_search/csv"
        print(f"URL: {url}")
        print(f"Sample params: game_date_gt={yesterday}, hfSea=2025|")
        
        response = requests.get(url, params=params, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response length: {len(response.text)} characters")
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            print(f"CSV lines: {len(lines)}")
            
            if len(lines) > 1:
                print("✅ Found Statcast data!")
                print(f"Headers: {lines[0][:200]}...")
                if len(lines) > 1:
                    print(f"Sample data: {lines[1][:200]}...")
            else:
                print("❌ No Statcast data found in response")
                print(f"Response content: {response.text[:500]}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Try with a specific game ID
    print("\n2. Testing with specific game ID (777483)...")
    game_params = params.copy()
    game_params['game_pk'] = '777483'
    
    try:
        response = requests.get(url, params=game_params, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response length: {len(response.text)} characters")
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            print(f"CSV lines: {len(lines)}")
            
            if len(lines) > 1:
                print("✅ Found game-specific data!")
                print(f"Headers: {lines[0][:200]}...")
                for i, line in enumerate(lines[1:6]):  # Show first 5 plays
                    print(f"Play {i+1}: {line[:150]}...")
            else:
                print("❌ No data for this game")
                print(f"Response: {response.text[:500]}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Try different date (maybe data isn't ready for yesterday)
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    print(f"\n3. Testing with older date ({two_days_ago})...")
    
    older_params = params.copy()
    older_params['game_date_gt'] = two_days_ago
    older_params['game_date_lt'] = two_days_ago
    
    try:
        response = requests.get(url, params=older_params, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            print(f"CSV lines: {len(lines)}")
            
            if len(lines) > 1:
                print("✅ Found data from 2 days ago!")
                print("This suggests data availability has a delay")
            else:
                print("❌ No data from 2 days ago either")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Check if Baseball Savant is working at all
    print("\n4. Testing Baseball Savant homepage...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"Homepage status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Baseball Savant is accessible")
        else:
            print("❌ Baseball Savant might be down")
    except Exception as e:
        print(f"❌ Error accessing homepage: {e}")
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print("- If no data found: Baseball Savant might have delays")
    print("- Data typically available 24-48 hours after games")
    print("- Season parameters might need adjustment")
    print("- API endpoints might have changed")

if __name__ == "__main__":
    test_baseball_savant_api() 