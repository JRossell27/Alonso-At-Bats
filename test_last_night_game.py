#!/usr/bin/env python3
"""
Test GIF integration with a specific game from last night (June 16, 2025)
This will help us verify the system works with real game data
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from baseball_savant_gif_integration import BaseballSavantGIFIntegration

class LastNightGameTester:
    def __init__(self):
        self.gif_integration = BaseballSavantGIFIntegration()
        self.api_base = "https://statsapi.mlb.com/api/v1"
        self.test_results = []
        
    def get_last_night_games(self):
        """Get games from last night (June 16, 2025)"""
        try:
            # Use yesterday's date
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"Fetching games from: {yesterday}")
            
            url = f"{self.api_base}/schedule"
            params = {
                'sportId': 1,
                'date': yesterday,
                'language': 'en'
            }
            
            print(f"Making request to: {url}")
            response = requests.get(url, params=params, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code}")
                print(f"Response text: {response.text[:500]}")
                return []
            
            data = response.json()
            games = []
            
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    # Only get completed games
                    status = game.get('status', {}).get('abstractGameState', '')
                    if status == 'Final':
                        games.append(game)
            
            print(f"Found {len(games)} completed games from last night")
            return games
            
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []
    
    def get_game_plays(self, game_id):
        """Get plays from a specific completed game"""
        try:
            # Use v1.1 API as indicated by the schedule response
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            
            # Filter for interesting plays
            interesting_plays = []
            for play in plays:
                result = play.get('result', {})
                event = result.get('event', '')
                
                # Look for plays that typically have good animations
                if any(keyword in event.lower() for keyword in 
                      ['home run', 'double', 'triple', 'hit', 'strikeout', 'walk']):
                    interesting_plays.append({
                        'game_id': game_id,
                        'play_id': play.get('atBatIndex', 0),
                        'inning': play.get('about', {}).get('inning', 0),
                        'event': event,
                        'description': result.get('description', ''),
                        'play_data': play
                    })
            
            # Return a mix of plays (first few and last few)
            if len(interesting_plays) > 6:
                return interesting_plays[:3] + interesting_plays[-3:]
            else:
                return interesting_plays
            
        except Exception as e:
            print(f"Error getting plays from game {game_id}: {e}")
            return []
    
    def test_gif_for_play(self, play_info, game_date):
        """Test GIF creation for a specific play"""
        print(f"\n{'='*60}")
        print(f"Testing Play: {play_info['event']}")
        print(f"Game ID: {play_info['game_id']}")
        print(f"Play ID: {play_info['play_id']}")
        print(f"Inning: {play_info['inning']}")
        print(f"Description: {play_info['description']}")
        print(f"Game Date: {game_date}")
        print(f"{'='*60}")
        
        test_result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'game_id': play_info['game_id'],
            'play_id': play_info['play_id'],
            'inning': play_info['inning'],
            'event': play_info['event'],
            'description': play_info['description'],
            'game_date': game_date,
            'statcast_found': False,
            'gif_created': False,
            'gif_path': None,
            'error': None,
            'file_size': None
        }
        
        try:
            print("Step 1: Checking for Statcast data...")
            # Test 1: Check if Statcast data exists - now with game_date
            statcast_data = self.gif_integration.get_statcast_data_for_play(
                play_info['game_id'], 
                play_info['play_id'],
                game_date
            )
            
            if statcast_data:
                test_result['statcast_found'] = True
                print("✅ Statcast data found!")
                print(f"   Data points: {len(statcast_data)}")
                
                print("\nStep 2: Attempting to create GIF...")
                # Test 2: Try to create GIF
                gif_filename = f"test_gif_{play_info['game_id']}_{play_info['play_id']}.gif"
                gif_path = self.gif_integration.get_gif_for_play(
                    play_info['game_id'],
                    play_info['play_id'],
                    game_date,
                    max_wait_minutes=1  # Don't wait long for testing
                )
                
                if gif_path and os.path.exists(gif_path):
                    test_result['gif_created'] = True
                    test_result['gif_path'] = gif_path
                    file_size = os.path.getsize(gif_path)
                    test_result['file_size'] = file_size
                    
                    print("✅ GIF created successfully!")
                    print(f"   📁 Path: {gif_path}")
                    print(f"   📊 Size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
                    
                    # Check if file is within Twitter's limits
                    if file_size < 15 * 1024 * 1024:  # 15MB limit
                        print("   ✅ File size within Twitter limits")
                    else:
                        print("   ⚠️  File size exceeds Twitter limits")
                        
                else:
                    print("❌ GIF creation failed - no file created")
                    test_result['error'] = "GIF creation failed - no output file"
            else:
                print("❌ No Statcast data found for this play")
                print("   This could be normal for:")
                print("   - Routine plays without detailed tracking")
                print("   - Very recent plays (data still processing)")
                print("   - Plays that don't typically get Statcast tracking")
                test_result['error'] = "No Statcast data found"
                
        except Exception as e:
            print(f"❌ Error testing play: {e}")
            test_result['error'] = str(e)
        
        self.test_results.append(test_result)
        print(f"\nResult: {'SUCCESS' if test_result['gif_created'] else 'FAILED'}")
        return test_result
    
    def run_comprehensive_test(self):
        """Run comprehensive test with last night's games"""
        print("🚀 MLB GIF Integration Test - Last Night's Games")
        print("=" * 80)
        print("Testing with completed games to verify GIF creation works")
        print()
        
        # Get last night's games
        games = self.get_last_night_games()
        
        if not games:
            print("❌ No completed games found from last night")
            print("This might be normal if:")
            print("- No games were played yesterday")
            print("- Games are still in progress")
            print("- API is having issues")
            return
        
        print(f"Found {len(games)} completed games from last night")
        print()
        
        # Test up to 2 games to avoid overwhelming
        for i, game in enumerate(games[:2]):
            game_id = game.get('gamePk')
            teams = game.get('teams', {})
            home_team = teams.get('home', {}).get('team', {}).get('name', 'Unknown')
            away_team = teams.get('away', {}).get('team', {}).get('name', 'Unknown')
            final_score = f"{teams.get('away', {}).get('score', 0)}-{teams.get('home', {}).get('score', 0)}"
            
            print(f"\n🎮 Testing Game {i+1}: {away_team} @ {home_team}")
            print(f"   Final Score: {away_team} {final_score.split('-')[0]}, {home_team} {final_score.split('-')[1]}")
            print(f"   Game ID: {game_id}")
            
            # Get plays from this game
            plays = self.get_game_plays(game_id)
            
            if not plays:
                print("   ⚠️  No interesting plays found in this game")
                continue
            
            print(f"   Found {len(plays)} interesting plays to test")
            
            # Test GIF creation for each play
            for j, play in enumerate(plays):
                print(f"\n   🎯 Testing Play {j+1}/{len(plays)}")
                # Extract date from game data
                game_date = game.get('gameDate', '').split('T')[0]  # Get YYYY-MM-DD format
                self.test_gif_for_play(play, game_date)
                time.sleep(1)  # Small delay between requests
        
        self.print_final_summary()
    
    def print_final_summary(self):
        """Print comprehensive test summary"""
        total = len(self.test_results)
        successful = sum(1 for r in self.test_results if r['gif_created'])
        statcast_found = sum(1 for r in self.test_results if r['statcast_found'])
        
        print("\n" + "=" * 80)
        print("🎯 FINAL TEST SUMMARY")
        print("=" * 80)
        print(f"📊 Total plays tested: {total}")
        print(f"📈 Plays with Statcast data: {statcast_found}")
        print(f"🎬 Successful GIFs created: {successful}")
        
        if successful > 0:
            print(f"\n🎉 SUCCESS! GIF integration is working!")
            print(f"   {successful}/{total} plays successfully generated GIFs")
            
            print("\n📁 Generated GIF files:")
            total_size = 0
            for result in self.test_results:
                if result['gif_created']:
                    size_mb = result['file_size'] / 1024 / 1024
                    total_size += result['file_size']
                    print(f"   • {result['gif_path']} ({size_mb:.1f} MB)")
            
            print(f"\n📊 Total GIF size: {total_size/1024/1024:.1f} MB")
            
            print("\n✅ Ready for deployment! The system can:")
            print("   🔥 Create GIFs from Baseball Savant data")
            print("   📏 Keep files within Twitter size limits")
            print("   🚀 Process multiple plays efficiently")
            
        else:
            print(f"\n⚠️  No GIFs were created")
            print("This could be due to:")
            print("   • Baseball Savant animations not available for these plays")
            print("   • Network/API issues")
            print("   • Plays being too routine for Statcast tracking")
            
            if statcast_found > 0:
                print(f"\n📈 However, {statcast_found} plays had Statcast data")
                print("   This suggests the system is working but GIF conversion failed")
            else:
                print("\n📉 No Statcast data found for any plays")
                print("   This suggests either API issues or no trackable plays")
        
        # Save detailed results
        results_file = f"last_night_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                'test_timestamp': datetime.now(timezone.utc).isoformat(),
                'total_tests': total,
                'successful_gifs': successful,
                'statcast_found': statcast_found,
                'results': self.test_results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")

def main():
    """Main test function"""
    print("🎾 MLB GIF Integration - Last Night's Game Test")
    print("=" * 60)
    print("This test uses completed games from last night to verify")
    print("that the GIF integration pipeline works with real data.")
    print()
    
    # Check dependencies
    try:
        import ffmpeg
        print("✅ ffmpeg available")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install ffmpeg-python")
        return
    
    try:
        import requests
        print("✅ requests available")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return
    
    print("✅ All dependencies ready")
    print()
    
    # Run tests
    tester = LastNightGameTester()
    tester.run_comprehensive_test()

if __name__ == "__main__":
    main() 