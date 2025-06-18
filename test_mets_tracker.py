#!/usr/bin/env python3
"""
Test Suite for Mets Home Run Tracker
Comprehensive testing for all system components
"""

import unittest
import time
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

# Import our modules
from mets_homerun_tracker import MetsHomeRunTracker, MetsHomeRun
from discord_integration import DiscordPoster, test_webhook
from mets_dashboard import app

class TestMetsHomeRunTracker(unittest.TestCase):
    """Test cases for the main tracker class"""
    
    def setUp(self):
        """Set up test environment"""
        self.tracker = MetsHomeRunTracker()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self.tracker, 'stop_monitoring'):
            self.tracker.stop_monitoring()
    
    def test_initialization(self):
        """Test tracker initialization"""
        self.assertEqual(self.tracker.mets_team_id, 121)
        self.assertIsNotNone(self.tracker.discord_webhook)
        self.assertIsNotNone(self.tracker.gif_generator)
        self.assertFalse(self.tracker.monitoring_active)
        self.assertIsInstance(self.tracker.processed_plays, set)
    
    @patch('requests.get')
    def test_get_live_mets_games(self, mock_get):
        """Test getting live Mets games"""
        # Mock response for live games
        mock_response = Mock()
        mock_response.json.return_value = {
            'dates': [{
                'games': [{
                    'gamePk': 12345,
                    'teams': {
                        'home': {'team': {'id': 121}},  # Mets home
                        'away': {'team': {'id': 111}}   # Other team
                    },
                    'status': {'statusCode': 'I'}  # Live game
                }]
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        games = self.tracker.get_live_mets_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]['gamePk'], 12345)
    
    @patch('requests.get')
    def test_get_game_plays(self, mock_get):
        """Test getting plays from a game"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'liveData': {
                'plays': {
                    'allPlays': [{
                        'about': {'atBatIndex': 1, 'inning': 5},
                        'result': {'event': 'Home Run', 'description': 'Test HR'},
                        'matchup': {
                            'batter': {'id': 1234, 'fullName': 'Pete Alonso'}
                        }
                    }]
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        plays = self.tracker.get_game_plays(12345)
        self.assertEqual(len(plays), 1)
    
    def test_mets_home_run_dataclass(self):
        """Test MetsHomeRun dataclass"""
        hr = MetsHomeRun(
            game_pk=12345,
            play_id="test_play",
            player_name="Pete Alonso",
            inning=5,
            description="Test home run",
            exit_velocity=105.5,
            launch_angle=25.0,
            hit_distance=420.0
        )
        
        self.assertEqual(hr.game_pk, 12345)
        self.assertEqual(hr.player_name, "Pete Alonso")
        self.assertEqual(hr.exit_velocity, 105.5)
        self.assertFalse(hr.discord_posted)
    
    @patch('requests.get')
    def test_is_mets_home_run(self, mock_get):
        """Test home run detection logic"""
        # Mock player info response
        mock_response = Mock()
        mock_response.json.return_value = {
            'people': [{
                'fullName': 'Pete Alonso',
                'currentTeam': {'id': 121}  # Mets team ID
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Mock play data
        play = {
            'result': {'event': 'Home Run', 'description': 'Test HR'},
            'matchup': {'batter': {'id': 1234}},
            'about': {'inning': 5, 'atBatIndex': 1, 'playIndex': 1}
        }
        
        home_run = self.tracker.is_mets_home_run(play, 12345)
        self.assertIsNotNone(home_run)
        self.assertEqual(home_run.player_name, 'Pete Alonso')

class TestDiscordIntegration(unittest.TestCase):
    """Test cases for Discord integration"""
    
    def setUp(self):
        """Set up Discord poster"""
        self.poster = DiscordPoster()
    
    def test_discord_poster_initialization(self):
        """Test Discord poster initialization"""
        self.assertIsNotNone(self.poster.webhook_url)
        self.assertIn('discord.com', self.poster.webhook_url)
    
    @patch('requests.post')
    def test_post_message(self, mock_post):
        """Test basic message posting"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.poster.post_message("Test message")
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('requests.post')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_post_message_with_gif(self, mock_open, mock_exists, mock_post):
        """Test posting message with GIF"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = Mock()
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.poster.post_message_with_gif("Test message", "/fake/path.gif")
        self.assertTrue(result)

class TestMetsHomeRunSystem(unittest.TestCase):
    """Integration tests for the complete system"""
    
    def setUp(self):
        """Set up system components"""
        self.tracker = MetsHomeRunTracker()
    
    def test_complete_workflow_simulation(self):
        """Test a complete home run processing workflow"""
        # Create a mock home run
        home_run = MetsHomeRun(
            game_pk=12345,
            play_id="test_12345_1_1",
            player_name="Pete Alonso",
            inning=5,
            description="Pete Alonso homers (15) on a fly ball to left center field.",
            exit_velocity=108.2,
            launch_angle=27.0,
            hit_distance=425.0
        )
        
        # Test data integrity
        self.assertEqual(home_run.player_name, "Pete Alonso")
        self.assertIsNotNone(home_run.timestamp)
        self.assertFalse(home_run.discord_posted)
        
        # Test queue management
        initial_processed = len(self.tracker.processed_plays)
        self.tracker.processed_plays.add(home_run.play_id)
        self.assertEqual(len(self.tracker.processed_plays), initial_processed + 1)

class TestMetsTrackerMonitoring(unittest.TestCase):
    """Test monitoring cycle functionality"""
    
    def setUp(self):
        self.tracker = MetsHomeRunTracker()
    
    @patch('time.sleep')
    @patch.object(MetsHomeRunTracker, 'get_live_mets_games')
    @patch.object(MetsHomeRunTracker, 'get_game_plays') 
    @patch.object(MetsHomeRunTracker, 'is_mets_home_run')
    def test_monitoring_cycle(self, mock_is_hr, mock_get_plays, mock_get_games, mock_sleep):
        """Test one monitoring cycle"""
        # Mock data
        mock_get_games.return_value = [{'gamePk': 12345}]
        mock_get_plays.return_value = [{'test': 'play'}]
        mock_is_hr.return_value = None  # No home runs found
        
        # Mock sleep to avoid actual waiting
        mock_sleep.side_effect = [None, KeyboardInterrupt()]  # Stop after one cycle
        
        # Start monitoring (should stop after KeyboardInterrupt)
        try:
            self.tracker.monitor_mets_home_runs()
        except KeyboardInterrupt:
            pass
        
        # Verify methods were called
        mock_get_games.assert_called()
        mock_get_plays.assert_called_with(12345)

class TestWebDashboard(unittest.TestCase):
    """Test cases for the web dashboard"""
    
    def setUp(self):
        """Set up Flask test client"""
        app.config['TESTING'] = True
        self.client = app.test_client()
    
    def test_dashboard_page(self):
        """Test main dashboard page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Mets Home Run Tracker', response.data)
    
    def test_status_api(self):
        """Test status API endpoint"""
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('monitoring', data)
        self.assertIn('stats', data)
    
    def test_ping_endpoint(self):
        """Test keep-alive ping endpoint"""
        response = self.client.get('/api/ping')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'alive')
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')

def run_system_test():
    """Run a comprehensive system test"""
    print("🧪 Running Mets Home Run Tracker System Test")
    print("=" * 50)
    
    test_results = []
    
    # Test 1: Basic initialization
    print("1. Testing system initialization...")
    try:
        tracker = MetsHomeRunTracker()
        test_results.append(("✅ PASS", "System initialization"))
    except Exception as e:
        test_results.append(("❌ FAIL", f"System initialization: {e}"))
    
    # Test 2: Discord integration
    print("2. Testing Discord integration...")
    try:
        poster = DiscordPoster()
        # Don't actually post to avoid spam, just test instantiation
        test_results.append(("✅ PASS", "Discord integration setup"))
    except Exception as e:
        test_results.append(("❌ FAIL", f"Discord integration: {e}"))
    
    # Test 3: GIF integration
    print("3. Testing GIF integration...")
    try:
        if hasattr(tracker, 'gif_generator'):
            test_results.append(("✅ PASS", "GIF integration setup"))
        else:
            test_results.append(("❌ FAIL", "GIF integration: missing gif_generator"))
    except Exception as e:
        test_results.append(("❌ FAIL", f"GIF integration: {e}"))
    
    # Test 4: Dashboard
    print("4. Testing web dashboard...")
    try:
        app.config['TESTING'] = True
        client = app.test_client()
        response = client.get('/')
        if response.status_code == 200:
            test_results.append(("✅ PASS", "Web dashboard"))
        else:
            test_results.append(("❌ FAIL", f"Web dashboard: HTTP {response.status_code}"))
    except Exception as e:
        test_results.append(("❌ FAIL", f"Web dashboard: {e}"))
    
    # Print results
    print("\n📊 Test Results:")
    print("-" * 30)
    passed = 0
    failed = 0
    
    for status, description in test_results:
        print(f"{status} {description}")
        if "PASS" in status:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! System ready for deployment.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
        return False

if __name__ == '__main__':
    # Run either unit tests or system test based on argument
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--system-test':
        success = run_system_test()
        sys.exit(0 if success else 1)
    else:
        # Run unit tests
        unittest.main(verbosity=2) 