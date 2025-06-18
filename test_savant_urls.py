#!/usr/bin/env python3
"""
Test the new Baseball Savant URL patterns with real game data
"""

import requests
import csv
from io import StringIO

def test_savant_url_patterns():
    """Test the Baseball Savant URL patterns with real data"""
    
    print("🔍 Testing Baseball Savant URL Patterns")
    print("=" * 60)
    
    # Get some real Statcast data from yesterday's game
    params = {
        'all': 'true',
        'hfGT': 'R|',
        'hfSea': '2025|',
        'game_date_gt': '2025-06-16',
        'game_date_lt': '2025-06-16',
        'game_pk': '777483',  # Phillies vs Marlins
        'min_results': '0',
        'type': 'details',
    }
    
    url = "https://baseballsavant.mlb.com/statcast_search/csv"
    response = requests.get(url, params=params, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Failed to get Statcast data: {response.status_code}")
        return
    
    # Parse CSV and get plays with events
    csv_reader = csv.DictReader(StringIO(response.text))
    plays_with_events = []
    
    for row in csv_reader:
        if row.get('events'):  # Only actual plays, not pitches
            plays_with_events.append(row)
    
    print(f"Found {len(plays_with_events)} plays with events")
    
    if not plays_with_events:
        print("❌ No plays found to test")
        return
    
    # Test URL patterns with first few plays
    base_url = "https://baseballsavant.mlb.com"
    game_id = '777483'
    
    print(f"\nTesting URL patterns for game {game_id}:")
    
    for i, play in enumerate(plays_with_events[:5]):  # Test first 5 plays
        sv_id = play.get('sv_id', '')
        at_bat_number = play.get('at_bat_number', '')
        event = play.get('events', '')
        
        print(f"\n🎯 Play {i+1}: {event}")
        print(f"   sv_id: {sv_id}")
        print(f"   at_bat_number: {at_bat_number}")
        
        # Test the documented URL patterns
        test_urls = []
        
        if sv_id:
            test_urls.append(f"{base_url}/sporty-videos?playId={sv_id}")
        
        if at_bat_number:
            test_urls.append(f"{base_url}/gf?game_pk={game_id}&at_bat_number={at_bat_number}")
        
        # Test each URL
        for url in test_urls:
            try:
                print(f"   Testing: {url}")
                response = requests.head(url, timeout=10, allow_redirects=True)
                content_type = response.headers.get('content-type', 'unknown')
                content_length = response.headers.get('content-length', 'unknown')
                
                print(f"   Status: {response.status_code}")
                print(f"   Content-Type: {content_type}")
                print(f"   Content-Length: {content_length}")
                
                if response.status_code == 200:
                    print("   ✅ URL accessible!")
                    
                    # If it's HTML, try to get the page to see if it contains video
                    if 'text/html' in content_type:
                        try:
                            page_response = requests.get(url, timeout=10)
                            if 'video' in page_response.text.lower():
                                print("   🎬 Page contains video content!")
                            else:
                                print("   📄 Page doesn't seem to contain video")
                        except:
                            print("   ⚠️  Couldn't fetch page content")
                else:
                    print(f"   ❌ Not accessible ({response.status_code})")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    print(f"\n{'='*60}")
    print("🎯 URL Pattern Test Complete")
    print("If any URLs returned 200 OK, the patterns are working!")

if __name__ == "__main__":
    test_savant_url_patterns() 