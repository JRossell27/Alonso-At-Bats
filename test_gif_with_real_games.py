#!/usr/bin/env python3
"""
Test GIF integration with real MLB games from today
Safe for deployment - outputs to files instead of Twitter
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timezone
from baseball_savant_gif_integration import BaseballSavantGIFIntegration

class MLBDataHelper:
    """Simplified MLB data fetcher for testing (no Twitter dependencies)"""
    def __init__(self):
        self.api_base = "https://statsapi.mlb.com/api/v1"
        
    def get_todays_games(self):
        """Get today's MLB games"""
        try:
            # Let's try with current actual date
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"Checking games for date: {today}")
            
            # Simplified API call
            url = f"{self.api_base}/schedule"
            params = {
                'sportId': 1,
                'date': today,
                'language': 'en'
            }
            
            print(f"Making request to: {url}")
            response = requests.get(url, params=params, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.text}")
                # Try yesterday's date if today doesn't work
                from datetime import timedelta
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"Trying yesterday's date: {yesterday}")
                params['date'] = yesterday
                response = requests.get(url, params=params, timeout=30)
                print(f"Yesterday response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            games = []
            
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    games.append(game)
            
            return games
            
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []
    
    def get_live_game_data(self, game_id):
        """Get live game data for a specific game"""
        try:
            url = f"{self.api_base}/game/{game_id}/feed/live"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching game data for {game_id}: {e}")
            return None

class GIFTestRunner:
    def __init__(self):
        self.gif_integration = BaseballSavantGIFIntegration()
        self.mlb_helper = MLBDataHelper()
        self.test_results = []
        
    def get_todays_games(self):
        """Get today's MLB games"""
        try:
            games_data = self.mlb_helper.get_todays_games()
            print(f"Found {len(games_data)} games today")
            
            # Filter for games that are live or recently completed
            active_games = []
            for game in games_data:
                status = game.get('status', {}).get('abstractGameState', '')
                if status in ['Live', 'Final']:
                    active_games.append(game)
                    
            print(f"Found {len(active_games)} active/completed games")
            return active_games
            
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []
    
    def get_recent_plays_from_game(self, game_id):
        """Get recent high-impact plays from a specific game"""
        try:
            game_data = self.mlb_helper.get_live_game_data(game_id)
            if not game_data:
                return []
                
            # Look for plays in the last few innings
            plays = game_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            
            # Get recent plays (last 5-10 plays)
            recent_plays = plays[-10:] if len(plays) > 10 else plays
            
            # Filter for plays likely to have good impact/animations
            interesting_plays = []
            for play in recent_plays:
                result = play.get('result', {})
                event = result.get('event', '')
                
                # Look for plays that typically have good animations
                if any(keyword in event.lower() for keyword in 
                      ['home run', 'double', 'triple', 'hit', 'error', 'out']):
                    interesting_plays.append({
                        'game_id': game_id,
                        'play_id': play.get('atBatIndex', 0),
                        'inning': play.get('about', {}).get('inning', 0),
                        'event': event,
                        'description': result.get('description', ''),
                        'play_data': play
                    })
                    
            return interesting_plays[-3:]  # Return last 3 interesting plays
            
        except Exception as e:
            print(f"Error getting plays from game {game_id}: {e}")
            return []
    
    def test_gif_for_play(self, play_info):
        """Test GIF creation for a specific play"""
        print(f"\n--- Testing GIF for play ---")
        print(f"Game ID: {play_info['game_id']}")
        print(f"Play ID: {play_info['play_id']}")
        print(f"Event: {play_info['event']}")
        print(f"Description: {play_info['description']}")
        
        test_result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'game_id': play_info['game_id'],
            'play_id': play_info['play_id'],
            'event': play_info['event'],
            'description': play_info['description'],
            'statcast_found': False,
            'gif_created': False,
            'gif_path': None,
            'error': None
        }
        
        try:
            # Test 1: Check if Statcast data exists
            statcast_data = self.gif_integration.get_statcast_data_for_play(
                play_info['game_id'], 
                play_info['play_id']
            )
            
            if statcast_data:
                test_result['statcast_found'] = True
                print("✅ Statcast data found!")
                
                # Test 2: Try to create GIF
                gif_path = self.gif_integration.create_gif_for_play(
                    play_info['game_id'],
                    play_info['play_id'],
                    f"test_gif_{play_info['game_id']}_{play_info['play_id']}.gif"
                )
                
                if gif_path and os.path.exists(gif_path):
                    test_result['gif_created'] = True
                    test_result['gif_path'] = gif_path
                    file_size = os.path.getsize(gif_path)
                    print(f"✅ GIF created successfully!")
                    print(f"   Path: {gif_path}")
                    print(f"   Size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
                else:
                    print("❌ GIF creation failed")
                    test_result['error'] = "GIF creation failed"
            else:
                print("❌ No Statcast data found for this play")
                test_result['error'] = "No Statcast data found"
                
        except Exception as e:
            print(f"❌ Error testing play: {e}")
            test_result['error'] = str(e)
        
        self.test_results.append(test_result)
        return test_result
    
    def run_comprehensive_test(self):
        """Run comprehensive test with today's games"""
        print("🏀 Starting GIF Integration Test with Real Games")
        print("=" * 60)
        
        # Get today's games
        games = self.get_todays_games()
        
        if not games:
            print("No active games found for testing")
            return
        
        # Test up to 3 games
        for i, game in enumerate(games[:3]):
            game_id = game.get('gamePk')
            home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'Unknown')
            away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'Unknown')
            
            print(f"\n🎮 Testing Game {i+1}: {away_team} @ {home_team} (ID: {game_id})")
            
            # Get recent plays from this game
            plays = self.get_recent_plays_from_game(game_id)
            
            if not plays:
                print("No interesting plays found in this game")
                continue
            
            # Test GIF creation for each play
            for play in plays:
                self.test_gif_for_play(play)
                time.sleep(2)  # Small delay between requests
        
        self.save_test_results()
        self.print_summary()
    
    def save_test_results(self):
        """Save test results to JSON file"""
        results_file = f"gif_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                'test_timestamp': datetime.now(timezone.utc).isoformat(),
                'total_tests': len(self.test_results),
                'successful_gifs': sum(1 for r in self.test_results if r['gif_created']),
                'results': self.test_results
            }, f, indent=2)
        
        print(f"\n💾 Test results saved to: {results_file}")
    
    def print_summary(self):
        """Print test summary"""
        total = len(self.test_results)
        successful = sum(1 for r in self.test_results if r['gif_created'])
        statcast_found = sum(1 for r in self.test_results if r['statcast_found'])
        
        print("\n" + "=" * 60)
        print("🎯 TEST SUMMARY")
        print("=" * 60)
        print(f"Total plays tested: {total}")
        print(f"Plays with Statcast data: {statcast_found}")
        print(f"Successful GIFs created: {successful}")
        
        if successful > 0:
            print(f"✅ SUCCESS! GIF integration is working!")
            print("\nGenerated GIF files:")
            for result in self.test_results:
                if result['gif_created']:
                    print(f"  - {result['gif_path']}")
        else:
            print("❌ No GIFs created - this might be normal if:")
            print("  - Games are too recent (animations not ready)")
            print("  - No high-impact plays occurred")
            print("  - Baseball Savant animations aren't available")

def main():
    """Main test function"""
    print("🚀 MLB GIF Integration Test")
    print("Testing with real games - safe for deployment")
    print("Results will be saved to files, not posted anywhere")
    print()
    
    # Check dependencies
    try:
        import ffmpeg
        print("✅ Dependencies OK")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return
    
    # Run tests
    test_runner = GIFTestRunner()
    test_runner.run_comprehensive_test()

if __name__ == "__main__":
    main() 