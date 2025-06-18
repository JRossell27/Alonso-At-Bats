#!/usr/bin/env python3
"""
Test video URL discovery using real play data from Baseball Savant
"""

import requests
import json
import re

def test_with_real_plays():
    """Test video URLs using real play data"""
    
    print("🎯 Testing with Real Play Data")
    print("=" * 60)
    
    # Get the game data we already fetched
    game_url = "https://baseballsavant.mlb.com/gf?game_pk=777483&at_bat_number=37"
    
    try:
        response = requests.get(game_url, timeout=15)
        data = response.json()
        
        # Look at the home team plays (Phillies batting)
        home_plays = data.get('team_home', [])
        print(f"Found {len(home_plays)} home team plays")
        
        # Find some interesting plays to test
        interesting_plays = []
        for play in home_plays[:10]:  # Check first 10 plays
            event = play.get('events', '')
            if event and any(keyword in event.lower() for keyword in ['home run', 'double', 'triple']):
                interesting_plays.append(play)
        
        print(f"Found {len(interesting_plays)} interesting plays to test")
        
        for i, play in enumerate(interesting_plays[:3]):  # Test first 3
            print(f"\n🎬 Testing Play {i+1}:")
            print(f"   Event: {play.get('events')}")
            print(f"   Description: {play.get('des', '')[:100]}...")
            print(f"   Play ID: {play.get('play_id')}")
            print(f"   At-bat: {play.get('ab_number')}")
            
            # Try different URL patterns with this specific play
            play_id = play.get('play_id', '')
            ab_number = play.get('ab_number', '')
            
            test_urls = []
            
            if play_id:
                test_urls.extend([
                    f"https://baseballsavant.mlb.com/sporty-videos?playId={play_id}",
                    f"https://baseballsavant.mlb.com/video/{play_id}",
                    f"https://baseballsavant.mlb.com/gf/video/{play_id}",
                ])
            
            if ab_number:
                test_urls.extend([
                    f"https://baseballsavant.mlb.com/sporty-videos?playId={ab_number}",
                    f"https://baseballsavant.mlb.com/gf?game_pk=777483&at_bat_number={ab_number}&video=true",
                    f"https://baseballsavant.mlb.com/video/game/{777483}/play/{ab_number}",
                ])
            
            print(f"   Testing {len(test_urls)} URL patterns:")
            
            for url in test_urls:
                try:
                    test_response = requests.head(url, timeout=10, allow_redirects=True)
                    content_type = test_response.headers.get('content-type', 'unknown')
                    
                    if test_response.status_code == 200:
                        print(f"   ✅ {url}")
                        print(f"      Status: {test_response.status_code}")
                        print(f"      Content-Type: {content_type}")
                        
                        # If it's HTML, check for video content
                        if 'text/html' in content_type:
                            try:
                                full_response = requests.get(url, timeout=10)
                                if any(term in full_response.text.lower() for term in ['<video', 'mp4', 'm3u8']):
                                    print(f"      🎬 Contains video content!")
                                else:
                                    print(f"      📄 HTML but no video detected")
                            except:
                                print(f"      ⚠️  Couldn't fetch full content")
                        
                        # If it's JSON, examine the data
                        elif 'application/json' in content_type:
                            try:
                                json_response = requests.get(url, timeout=10)
                                json_data = json_response.json()
                                print(f"      📊 JSON response with keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
                            except:
                                print(f"      📊 JSON response (couldn't parse)")
                    else:
                        print(f"   ❌ {url}: {test_response.status_code}")
                        
                except Exception as e:
                    print(f"   ❌ {url}: Error - {str(e)[:50]}...")
        
        # Also test with different game endpoint patterns
        print(f"\n🎮 Testing alternate game endpoints:")
        game_patterns = [
            f"https://baseballsavant.mlb.com/gf/video?game_pk=777483",
            f"https://baseballsavant.mlb.com/api/game/777483/videos",
            f"https://baseballsavant.mlb.com/game/777483/highlights",
            f"https://baseballsavant.mlb.com/illustrator/game/777483",
        ]
        
        for url in game_patterns:
            try:
                test_response = requests.head(url, timeout=10)
                if test_response.status_code == 200:
                    print(f"   ✅ {url}: {test_response.status_code}")
                else:
                    print(f"   ❌ {url}: {test_response.status_code}")
            except Exception as e:
                print(f"   ❌ {url}: Error")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_with_real_plays() 