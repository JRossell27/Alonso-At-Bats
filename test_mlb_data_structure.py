#!/usr/bin/env python3
"""
Test script to examine the actual MLB API data structure 
and see what win probability data is available
"""

import requests
import json
from datetime import datetime, timedelta
import pytz

def get_yesterday_date():
    """Get yesterday's date in MM/DD/YYYY format"""
    eastern_tz = pytz.timezone('US/Eastern')
    yesterday = datetime.now(eastern_tz) - timedelta(days=1)
    return yesterday.strftime("%m/%d/%Y")

def examine_mlb_api_structure():
    """Examine what data is available in MLB API"""
    
    yesterday = get_yesterday_date()
    print(f"🔍 Examining MLB API data structure for {yesterday}")
    print("=" * 60)
    
    # Get games for yesterday
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": yesterday,
        "hydrate": "game(content(editorial(recap))),decisions,person,probablePitcher,stats,homeRuns,previousPlay,team"
    }
    
    print("📡 Fetching games data...")
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch games: {response.status_code}")
        return
    
    games_data = response.json()
    
    if not games_data.get('dates') or not games_data['dates']:
        print("❌ No games found for yesterday")
        return
    
    # Get first game ID for detailed analysis
    game = games_data['dates'][0]['games'][0]
    game_id = game['gamePk']
    
    print(f"🎮 Examining game {game_id}: {game['teams']['away']['team']['name']} @ {game['teams']['home']['team']['name']}")
    
    # Get detailed play-by-play data
    pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    
    print("📡 Fetching play-by-play data...")
    pbp_response = requests.get(pbp_url)
    
    if pbp_response.status_code != 200:
        print(f"❌ Failed to fetch play-by-play: {pbp_response.status_code}")
        return
    
    pbp_data = pbp_response.json()
    
    # Examine structure
    print("\n🏗️  MLB API Data Structure:")
    print(f"Top-level keys: {list(pbp_data.keys())}")
    
    if 'liveData' in pbp_data:
        live_data = pbp_data['liveData']
        print(f"liveData keys: {list(live_data.keys())}")
        
        if 'plays' in live_data:
            plays = live_data['plays']
            print(f"plays keys: {list(plays.keys())}")
            
            if 'allPlays' in plays:
                all_plays = plays['allPlays']
                print(f"Total plays: {len(all_plays)}")
                
                # Examine first few plays
                for i, play in enumerate(all_plays[:3]):
                    print(f"\n📋 Play {i+1} structure:")
                    print(f"  Top-level keys: {list(play.keys())}")
                    
                    # Check for win probability data
                    if 'playEvents' in play:
                        events = play['playEvents']
                        print(f"  playEvents count: {len(events)}")
                        if events:
                            print(f"  First event keys: {list(events[0].keys())}")
                            
                            # Look for win probability
                            for j, event in enumerate(events):
                                if 'winProbability' in event:
                                    print(f"  ✅ FOUND winProbability in event {j}: {event['winProbability']}")
                                if 'leverageIndex' in event:
                                    print(f"  ✅ FOUND leverageIndex in event {j}: {event['leverageIndex']}")
                    
                    if 'about' in play:
                        about = play['about']
                        print(f"  about keys: {list(about.keys())}")
                        if 'leverageIndex' in about:
                            print(f"  ✅ FOUND leverageIndex in about: {about['leverageIndex']}")
                    
                    if 'result' in play:
                        result = play['result']
                        print(f"  result keys: {list(result.keys())}")
                        if 'event' in result:
                            print(f"  Event: {result['event']}")
                        if 'description' in result:
                            print(f"  Description: {result['description'][:100]}...")
                    
                    # Check for pre/post win probability
                    if 'prePlayWinProbability' in play:
                        print(f"  ✅ FOUND prePlayWinProbability: {play['prePlayWinProbability']}")
                    if 'postPlayWinProbability' in play:
                        print(f"  ✅ FOUND postPlayWinProbability: {play['postPlayWinProbability']}")
    
    # Try the enhanced API endpoint
    print(f"\n🔬 Trying enhanced API endpoint...")
    enhanced_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live?hydrate=plays(events)"
    enhanced_response = requests.get(enhanced_url)
    
    if enhanced_response.status_code == 200:
        enhanced_data = enhanced_response.json()
        if 'liveData' in enhanced_data and 'plays' in enhanced_data['liveData']:
            plays = enhanced_data['liveData']['plays']['allPlays']
            print(f"Enhanced API plays count: {len(plays)}")
            
            # Look for win probability in enhanced data
            win_prob_found = False
            for i, play in enumerate(plays[:5]):
                if 'playEvents' in play:
                    for event in play['playEvents']:
                        if 'winProbability' in event:
                            print(f"  ✅ Enhanced API winProbability found in play {i}: {event['winProbability']}")
                            win_prob_found = True
                        if 'leverageIndex' in event:
                            print(f"  ✅ Enhanced API leverageIndex found in play {i}: {event['leverageIndex']}")
            
            if not win_prob_found:
                print("  ❌ No winProbability found in enhanced API either")
    
    print("\n" + "=" * 60)
    print("🎯 CONCLUSION:")
    print("   This analysis will show us exactly what win probability data")
    print("   is available from MLB's API and how to access it properly.")

if __name__ == "__main__":
    examine_mlb_api_structure() 