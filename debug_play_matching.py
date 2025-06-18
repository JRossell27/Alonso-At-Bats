#!/usr/bin/env python3
"""
Debug play matching between MLB API and Statcast data
"""

import requests
import csv
from io import StringIO

def debug_play_matching():
    """Debug the play matching logic"""
    
    print("🔍 Debugging Play Matching")
    print("=" * 60)
    
    game_id = 777483
    game_date = '2025-06-16'
    
    # Step 1: Get MLB API data
    print("Step 1: Getting MLB API data...")
    mlb_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    mlb_response = requests.get(mlb_url, timeout=30)
    mlb_data = mlb_response.json()
    
    plays = mlb_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    
    print(f"Found {len(plays)} total plays in MLB API")
    
    # Find home runs
    home_runs = []
    for play in plays:
        result = play.get('result', {})
        event = result.get('event', '')
        if 'Home Run' in event:
            home_runs.append(play)
    
    print(f"Found {len(home_runs)} home runs:")
    for i, hr in enumerate(home_runs):
        print(f"  {i+1}. Inning {hr['about']['inning']}, {hr['result']['description']}")
        print(f"      Batter: {hr['matchup']['batter']['fullName']}")
        print(f"      At-bat index: {hr['atBatIndex']}")
    
    # Step 2: Get Statcast data
    print(f"\nStep 2: Getting Statcast data...")
    params = {
        'all': 'true',
        'hfGT': 'R|',
        'hfSea': '2025|',
        'game_date_gt': game_date,
        'game_date_lt': game_date,
        'game_pk': game_id,
        'min_results': '0',
        'type': 'details',
    }
    
    url = "https://baseballsavant.mlb.com/statcast_search/csv"
    response = requests.get(url, params=params, timeout=30)
    
    if response.status_code == 200:
        csv_reader = csv.DictReader(StringIO(response.text))
        
        # Get plays with events
        statcast_plays = []
        for row in csv_reader:
            if row.get('events'):
                statcast_plays.append(row)
        
        print(f"Found {len(statcast_plays)} Statcast plays with events")
        
        # Find home runs in Statcast
        statcast_hrs = []
        for play in statcast_plays:
            event = play.get('events', '').lower()
            if 'home' in event and 'run' in event:
                statcast_hrs.append(play)
        
        print(f"Found {len(statcast_hrs)} home runs in Statcast:")
        for i, hr in enumerate(statcast_hrs):
            print(f"  {i+1}. Inning {hr.get('inning')}, {hr.get('events')}")
            print(f"      Player: {hr.get('player_name')}")
            print(f"      Play ID: {hr.get('play_id')}")
            print(f"      Description: {hr.get('des', '')[:100]}...")
        
        # Step 3: Check if any Statcast plays have play_id
        print(f"\nStep 3: Checking for play_id field in Statcast data...")
        plays_with_ids = [play for play in statcast_plays if play.get('play_id')]
        print(f"Plays with play_id: {len(plays_with_ids)}")
        
        if plays_with_ids:
            print("Sample play_id values:")
            for i, play in enumerate(plays_with_ids[:5]):
                print(f"  {i+1}. {play.get('play_id')} - {play.get('events')}")
        
        # Step 4: Check all available fields
        print(f"\nStep 4: Available fields in Statcast data:")
        if statcast_plays:
            fields = list(statcast_plays[0].keys())
            print(f"Total fields: {len(fields)}")
            
            # Look for ID-like fields
            id_fields = [f for f in fields if 'id' in f.lower() or 'uuid' in f.lower()]
            print(f"ID-like fields: {id_fields}")
            
            # Show some key fields
            key_fields = ['play_id', 'game_pk', 'sv_id', 'at_bat_number', 'events', 'player_name']
            print(f"\nKey field values for first home run:")
            for play in statcast_hrs[:1]:
                for field in key_fields:
                    print(f"  {field}: {play.get(field, 'N/A')}")
        
        # Step 5: Try to match MLB and Statcast home runs
        print(f"\nStep 5: Attempting to match MLB and Statcast home runs...")
        
        if home_runs and statcast_hrs:
            mlb_hr = home_runs[0]  # First home run from MLB
            target_inning = mlb_hr['about']['inning']
            target_batter = mlb_hr['matchup']['batter']['fullName']
            
            print(f"Looking for: {target_batter} home run in inning {target_inning}")
            
            for statcast_hr in statcast_hrs:
                statcast_inning = statcast_hr.get('inning')
                statcast_player = statcast_hr.get('player_name', '')
                
                print(f"  Checking: {statcast_player} in inning {statcast_inning}")
                
                if str(statcast_inning) == str(target_inning):
                    print(f"  ✅ Inning match!")
                    if target_batter.split()[-1] in statcast_player or statcast_player.split()[-1] in target_batter:
                        print(f"  ✅ Player match! This is our play")
                        print(f"      Play ID: {statcast_hr.get('play_id')}")
                        print(f"      SV ID: {statcast_hr.get('sv_id')}")
                        break
    
    else:
        print(f"❌ Failed to get Statcast data: {response.status_code}")

if __name__ == "__main__":
    debug_play_matching() 