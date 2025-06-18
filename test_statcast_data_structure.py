#!/usr/bin/env python3
"""
Examine the structure of Statcast data to understand how to match plays
"""

import requests
import csv
from io import StringIO

def examine_statcast_structure():
    """Examine what fields are available in Statcast data"""
    
    # Get data for a specific game
    params = {
        'all': 'true',
        'hfGT': 'R|',
        'hfSea': '2025|',
        'game_date_gt': '2025-06-16',
        'game_date_lt': '2025-06-16',
        'game_pk': '777483',  # The Phillies vs Marlins game
        'min_results': '0',
        'type': 'details',
    }
    
    url = "https://baseballsavant.mlb.com/statcast_search/csv"
    response = requests.get(url, params=params, timeout=30)
    
    if response.status_code == 200:
        # Parse CSV
        csv_reader = csv.DictReader(StringIO(response.text))
        
        # Get first few rows
        rows = []
        for i, row in enumerate(csv_reader):
            if i < 10:  # First 10 plays
                rows.append(row)
            else:
                break
        
        if rows:
            print("🔍 Statcast Data Structure Analysis")
            print("=" * 60)
            print(f"Total columns: {len(rows[0])}")
            print("\nColumn names:")
            for i, col in enumerate(rows[0].keys()):
                print(f"  {i+1:2d}. {col}")
            
            print("\n📊 Sample Data (first 3 plays):")
            for i, row in enumerate(rows[:3]):
                print(f"\nPlay {i+1}:")
                print(f"  at_bat_number: {row.get('at_bat_number', 'N/A')}")
                print(f"  events: {row.get('events', 'N/A')}")
                print(f"  description: {row.get('description', 'N/A')}")
                print(f"  inning: {row.get('inning', 'N/A')}")
                print(f"  inning_topbot: {row.get('inning_topbot', 'N/A')}")
                print(f"  player_name: {row.get('player_name', 'N/A')}")
                print(f"  pitch_type: {row.get('pitch_type', 'N/A')}")
                print(f"  game_pk: {row.get('game_pk', 'N/A')}")
                print(f"  sv_id: {row.get('sv_id', 'N/A')}")
            
            # Look for unique events (actual plays vs pitches)
            events = {}
            at_bat_numbers = set()
            
            for row in rows:
                event = row.get('events', '')
                at_bat = row.get('at_bat_number', '')
                if event:  # Only count rows with actual events
                    events[event] = events.get(event, 0) + 1
                if at_bat:
                    at_bat_numbers.add(at_bat)
            
            print(f"\n🎯 Events found in sample:")
            for event, count in events.items():
                print(f"  {event}: {count}")
            
            print(f"\n🔢 At-bat numbers: {sorted(at_bat_numbers)}")
            
            # Filter to show only plays with events (not individual pitches)
            play_rows = [row for row in rows if row.get('events')]
            
            print(f"\n🎪 Actual plays (not pitches): {len(play_rows)}")
            for i, row in enumerate(play_rows):
                print(f"  Play {i+1}: {row.get('events')} (at_bat: {row.get('at_bat_number')})")
                print(f"    Description: {row.get('description')}")
                print(f"    sv_id: {row.get('sv_id', 'N/A')}")
                
        else:
            print("No data found")
    else:
        print(f"Error: {response.status_code}")

if __name__ == "__main__":
    examine_statcast_structure() 