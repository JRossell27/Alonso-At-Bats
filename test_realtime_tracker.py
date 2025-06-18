#!/usr/bin/env python3
"""
Test script for Real-Time MLB Impact Plays Tracker
Tests the core functionality without actually posting to Twitter
"""

import os
import sys
import time
import logging
from datetime import datetime
from realtime_impact_tracker import RealTimeImpactTracker

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_live_games():
    """Test fetching live games"""
    print("🔍 Testing live games fetch...")
    tracker = RealTimeImpactTracker()
    
    # Override Twitter setup to avoid authentication errors
    tracker.twitter_api = None
    
    games = tracker.get_live_games()
    print(f"Found {len(games)} live/recent games")
    
    for game in games[:3]:  # Show first 3 games
        home = game.get('teams', {}).get('home', {}).get('team', {}).get('abbreviation', 'HOME')
        away = game.get('teams', {}).get('away', {}).get('team', {}).get('abbreviation', 'AWAY')
        status = game.get('status', {}).get('statusCode', '')
        game_id = game.get('gamePk', 'N/A')
        
        print(f"  📍 Game {game_id}: {away} @ {home} (Status: {status})")
    
    return games

def test_game_plays(game_id):
    """Test fetching plays from a specific game"""
    print(f"\n🎯 Testing plays fetch for game {game_id}...")
    tracker = RealTimeImpactTracker()
    tracker.twitter_api = None
    
    plays = tracker.get_game_plays(game_id)
    print(f"Found {len(plays)} plays in game {game_id}")
    
    high_impact_plays = []
    for play in plays:
        impact = tracker.calculate_impact_score(play)
        leverage = play.get('leverage_index', 1.0)
        
        if tracker.is_high_impact_play(impact, leverage):
            high_impact_plays.append((play, impact))
            print(f"  🔥 HIGH IMPACT: {impact:.1%} - {play.get('description', 'No description')[:60]}...")
    
    print(f"\nFound {len(high_impact_plays)} high-impact plays")
    return high_impact_plays

def test_graphic_creation(play, game_info, impact_score):
    """Test creating a graphic for a play"""
    print(f"\n🎨 Testing graphic creation...")
    tracker = RealTimeImpactTracker()
    tracker.twitter_api = None
    
    graphic_file = tracker.create_play_graphic(play, game_info, impact_score)
    if graphic_file:
        print(f"✅ Created graphic: {graphic_file}")
        
        # Check file size
        if os.path.exists(graphic_file):
            size = os.path.getsize(graphic_file)
            print(f"  📊 File size: {size:,} bytes")
            
            # Clean up
            os.remove(graphic_file)
            print(f"  🧹 Cleaned up test file")
        
        return True
    else:
        print("❌ Failed to create graphic")
        return False

def test_tweet_formatting(play, game_info, impact_score):
    """Test tweet text formatting"""
    print(f"\n📝 Testing tweet formatting...")
    tracker = RealTimeImpactTracker()
    tracker.twitter_api = None
    
    tweet_text = tracker.format_tweet_text(play, game_info, impact_score)
    print(f"Tweet text ({len(tweet_text)} chars):")
    print("-" * 50)
    print(tweet_text)
    print("-" * 50)
    
    return tweet_text

def main():
    """Run all tests"""
    print("🔥 Testing Real-Time MLB Impact Plays Tracker")
    print("=" * 60)
    
    # Test 1: Get live games
    games = test_live_games()
    
    if not games:
        print("⚠️ No live games found - this is normal during off-season or off-hours")
        print("The system will work when games are live!")
        return
    
    # Test 2: Get plays from first game
    first_game = games[0]
    game_id = first_game.get('gamePk')
    
    game_info = {
        'home_team': first_game.get('teams', {}).get('home', {}).get('team', {}).get('abbreviation', 'HOME'),
        'away_team': first_game.get('teams', {}).get('away', {}).get('team', {}).get('abbreviation', 'AWAY'),
        'status': first_game.get('status', {}).get('statusCode', ''),
        'game_id': game_id
    }
    
    high_impact_plays = test_game_plays(game_id)
    
    if high_impact_plays:
        # Test with first high-impact play
        play, impact_score = high_impact_plays[0]
        
        # Test 3: Create graphic
        test_graphic_creation(play, game_info, impact_score)
        
        # Test 4: Format tweet
        test_tweet_formatting(play, game_info, impact_score)
        
    else:
        print("⚠️ No high-impact plays found in this game")
        print("The system will detect and tweet them when they occur!")
    
    print("\n✅ All tests completed!")
    print("\n🚀 To start real-time monitoring:")
    print("   python realtime_impact_tracker.py")
    print("   Visit: http://localhost:5000")
    print("   Click: http://localhost:5000/start")

if __name__ == "__main__":
    main() 