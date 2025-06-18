#!/usr/bin/env python3
"""
Mets Home Run Tracker
Real-time monitoring of ALL New York Mets home runs with GIF generation and Discord posting
"""

import requests
import time
import logging
import os
import pickle
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from threading import Thread
import queue
import json

# Import our modules
from discord_integration import post_home_run
from baseball_savant_gif_integration import BaseballSavantGIFIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mets_homerun_tracker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@dataclass
class MetsHomeRun:
    """Data structure for a Mets home run"""
    game_pk: int
    play_id: str
    player_name: str
    inning: int
    description: str
    exit_velocity: Optional[float] = None
    launch_angle: Optional[float] = None
    hit_distance: Optional[float] = None
    gif_path: Optional[str] = None
    discord_posted: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    attempts: int = 0

class MetsHomeRunTracker:
    """Main tracker class for Mets home runs"""
    
    def __init__(self):
        self.mets_team_id = 121  # New York Mets team ID
        self.monitoring_active = False
        self.processed_plays: Set[str] = set()
        self.home_run_queue = queue.Queue()
        self.start_time = datetime.now()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        
        # Discord integration
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        if not self.discord_webhook:
            logger.error("❌ DISCORD_WEBHOOK_URL environment variable not set!")
            raise ValueError("DISCORD_WEBHOOK_URL environment variable is required")
        
        # Initialize GIF generator
        try:
            self.gif_generator = BaseballSavantGIFIntegration()
            logger.info("🎬 GIF integration initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GIF generator: {e}")
            self.gif_generator = None
        
        # Statistics
        self.stats = {
            'homeruns_posted_today': 0,
            'gifs_created_today': 0,
            'homeruns_queued_today': 0,
            'last_check': None,
            'processed_plays': 0,
            'api_calls_today': 0,
            'errors_today': 0
        }
        
        # Load processed plays from file
        self.load_processed_plays()
        
        logger.info("🏠⚾ Mets Home Run Tracker initialized")
        logger.info(f"📊 Loaded {len(self.processed_plays)} previously processed plays")
    
    def load_processed_plays(self):
        """Load processed plays from pickle file"""
        try:
            if os.path.exists('processed_mets_hrs.pkl'):
                with open('processed_mets_hrs.pkl', 'rb') as f:
                    self.processed_plays = pickle.load(f)
                logger.info(f"📂 Loaded {len(self.processed_plays)} processed plays from file")
            else:
                logger.info("📂 No processed plays file found, starting fresh")
        except Exception as e:
            logger.error(f"❌ Error loading processed plays: {e}")
            self.processed_plays = set()
    
    def save_processed_plays(self):
        """Save processed plays to pickle file"""
        try:
            # Keep only recent plays (last 30 days) to manage memory
            cutoff_date = datetime.now() - timedelta(days=30)
            recent_plays = set()
            
            for play_id in self.processed_plays:
                # Simple heuristic: keep all plays if we can't determine date
                recent_plays.add(play_id)
            
            # Limit to last 200 plays to avoid memory issues
            if len(recent_plays) > 200:
                recent_plays = set(list(recent_plays)[-200:])
            
            self.processed_plays = recent_plays
            
            with open('processed_mets_hrs.pkl', 'wb') as f:
                pickle.dump(self.processed_plays, f)
            
        except Exception as e:
            logger.error(f"❌ Error saving processed plays: {e}")
    
    def get_live_mets_games(self) -> List[Dict]:
        """Get live Mets games from MLB API"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&teamId={self.mets_team_id}"
            
            self.stats['api_calls_today'] += 1
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            games = []
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    # Include live, preview, and recently completed games
                    status_code = game.get('status', {}).get('statusCode', '')
                    status_desc = game.get('status', {}).get('detailedState', 'Unknown')
                    
                    # Log game information
                    away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'Unknown')
                    home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'Unknown')
                    
                    if status_code in ['I', 'P', 'S', 'F']:  # Live, Preview, Scheduled, Final
                        games.append(game)
                        logger.info(f"🎯 Monitoring game: {away_team} @ {home_team} - Status: {status_desc}")
            
            # Reset consecutive errors on success
            self.consecutive_errors = 0
            
            return games
            
        except Exception as e:
            self.consecutive_errors += 1
            self.stats['errors_today'] += 1
            logger.error(f"❌ Error getting live games (attempt {self.consecutive_errors}): {e}")
            
            if self.consecutive_errors >= self.max_consecutive_errors:
                logger.error(f"🚨 Too many consecutive errors ({self.consecutive_errors}), implementing backoff")
                time.sleep(300)  # 5 minute backoff
                self.consecutive_errors = 0
            
            return []
    
    def get_game_plays(self, game_pk: int) -> List[Dict]:
        """Get all plays from a specific game"""
        try:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
            self.stats['api_calls_today'] += 1
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            
            # Log current game state
            game_data = data.get('gameData', {})
            status = game_data.get('status', {}).get('detailedState', 'Unknown')
            current_inning = data.get('liveData', {}).get('linescore', {}).get('currentInning', 'N/A')
            inning_state = data.get('liveData', {}).get('linescore', {}).get('inningState', '')
            
            logger.info(f"🔍 Game {game_pk}: {status} - Inning {current_inning} {inning_state} - {len(plays)} total plays")
            
            return plays
            
        except Exception as e:
            logger.error(f"❌ Error getting plays for game {game_pk}: {e}")
            self.stats['errors_today'] += 1
            return []
    
    def get_player_info(self, player_id: int) -> Dict:
        """Get player information from MLB API"""
        try:
            url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
            self.stats['api_calls_today'] += 1
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('people'):
                return data['people'][0]
            return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting player info for {player_id}: {e}")
            self.stats['errors_today'] += 1
            return {}
    
    def get_enhanced_statcast_data(self, play: Dict, game_pk: int) -> Dict[str, Any]:
        """Extract enhanced Statcast data from play"""
        stats = {
            'exit_velocity': None,
            'launch_angle': None,
            'distance': None
        }
        
        try:
            # Try to get Statcast data from play data
            play_events = play.get('playEvents', [])
            for event in play_events:
                hit_data = event.get('hitData', {})
                if hit_data:
                    stats['exit_velocity'] = hit_data.get('launchSpeed')
                    stats['launch_angle'] = hit_data.get('launchAngle')
                    stats['distance'] = hit_data.get('totalDistance')
                    break
            
            # Also check in playEvents for additional data
            if not any(stats.values()):
                for event in play_events:
                    if event.get('details', {}).get('event') == 'Hit Into Play':
                        hit_data = event.get('hitData', {})
                        if hit_data:
                            stats['exit_velocity'] = hit_data.get('launchSpeed')
                            stats['launch_angle'] = hit_data.get('launchAngle') 
                            stats['distance'] = hit_data.get('totalDistance')
                            break
            
        except Exception as e:
            logger.error(f"❌ Error extracting Statcast data: {e}")
        
        return stats
    
    def is_mets_home_run(self, play: Dict, game_pk: int) -> Optional[MetsHomeRun]:
        """Check if a play is a Mets home run"""
        try:
            # Check if it's a home run
            result = play.get('result', {})
            if result.get('event') != 'Home Run':
                return None
            
            # Get batter info
            matchup = play.get('matchup', {})
            batter_id = matchup.get('batter', {}).get('id')
            
            if not batter_id:
                return None
            
            # Check if batter is on the Mets
            player_info = self.get_player_info(batter_id)
            current_team = player_info.get('currentTeam', {})
            
            if current_team.get('id') != self.mets_team_id:
                return None
            
            # Create unique play ID
            about = play.get('about', {})
            inning = about.get('inning', 0)
            at_bat_index = about.get('atBatIndex', 0)
            play_index = about.get('playIndex', 0)
            play_id = f"mets_hr_{game_pk}_{inning}_{at_bat_index}_{play_index}"
            
            # Check if already processed
            if play_id in self.processed_plays:
                return None
            
            # Get enhanced Statcast data
            stats = self.get_enhanced_statcast_data(play, game_pk)
            
            # Create MetsHomeRun object
            home_run = MetsHomeRun(
                game_pk=game_pk,
                play_id=play_id,
                player_name=player_info.get('fullName', 'Unknown Player'),
                inning=inning,
                description=result.get('description', 'Home run'),
                exit_velocity=stats.get('exit_velocity'),
                launch_angle=stats.get('launch_angle'),
                hit_distance=stats.get('distance')
            )
            
            logger.info(f"🏠⚾ NEW METS HOME RUN DETECTED!")
            logger.info(f"🎯 Player: {home_run.player_name}")
            logger.info(f"📍 Inning: {inning}")
            logger.info(f"🚀 Exit Velocity: {stats.get('exit_velocity', 'N/A')} mph")
            logger.info(f"📐 Launch Angle: {stats.get('launch_angle', 'N/A')}°")
            logger.info(f"📏 Distance: {stats.get('distance', 'N/A')} ft")
            
            return home_run
            
        except Exception as e:
            logger.error(f"❌ Error checking if play is Mets home run: {e}")
            return None
    
    def process_gif_queue(self):
        """Process the GIF queue in background"""
        logger.info("🎬 Starting GIF processing thread")
        
        while self.monitoring_active:
            try:
                if not self.home_run_queue.empty():
                    home_run = self.home_run_queue.get_nowait()
                    
                    if home_run.attempts >= 5:
                        logger.warning(f"⚠️ Max attempts reached for {home_run.player_name} HR - skipping")
                        continue
                    
                    # Increment attempts
                    home_run.attempts += 1
                    logger.info(f"🔄 Processing {home_run.player_name} HR (attempt {home_run.attempts}/5)")
                    
                    # Try to create GIF
                    if self.gif_generator:
                        try:
                            # Get game date for Baseball Savant
                            game_date = datetime.now().strftime('%Y-%m-%d')
                            
                            # Create a simple MLB play data structure for the GIF generator
                            mlb_play_data = {
                                'result': {'event': 'Home Run'},
                                'about': {'inning': home_run.inning},
                                'matchup': {'batter': {'id': None}}
                            }
                            
                            logger.info(f"🎬 Attempting to create GIF for {home_run.player_name} HR...")
                            gif_path = self.gif_generator.get_gif_for_play(
                                home_run.game_pk,
                                0,  # play_id - we'll use 0 as placeholder
                                game_date,
                                mlb_play_data
                            )
                            home_run.gif_path = gif_path
                            
                            if gif_path:
                                self.stats['gifs_created_today'] += 1
                                logger.info(f"✅ GIF created successfully: {gif_path}")
                            else:
                                logger.warning(f"⚠️ No GIF created for {home_run.player_name} HR")
                        except Exception as e:
                            logger.error(f"❌ Error creating GIF: {e}")
                    
                    # Post to Discord
                    logger.info(f"🎉 Posting {home_run.player_name} HR to Discord...")
                    stats_dict = {
                        'exit_velocity': home_run.exit_velocity,
                        'launch_angle': home_run.launch_angle,
                        'distance': home_run.hit_distance
                    }
                    
                    success = post_home_run(
                        home_run.player_name,
                        home_run.description,
                        stats_dict,
                        home_run.gif_path
                    )
                    
                    if success:
                        home_run.discord_posted = True
                        self.stats['homeruns_posted_today'] += 1
                        logger.info(f"✅ Successfully posted {home_run.player_name} HR to Discord!")
                        logger.info(f"🎉 Posted to #LGM Discord channel - Let's Go Mets!")
                        
                        # Clean up GIF file
                        if home_run.gif_path and os.path.exists(home_run.gif_path):
                            try:
                                os.remove(home_run.gif_path)
                                logger.info(f"🗑️ Cleaned up GIF file: {home_run.gif_path}")
                            except Exception as e:
                                logger.error(f"❌ Error removing GIF file: {e}")
                    else:
                        # Requeue with delay if failed
                        if home_run.attempts < 5:
                            logger.warning(f"⚠️ Failed to post {home_run.player_name} HR, requeueing (attempt {home_run.attempts})")
                            time.sleep(60)  # Wait before retry
                            self.home_run_queue.put(home_run)
                        else:
                            logger.error(f"💥 Failed to post {home_run.player_name} HR after 5 attempts")
                
                time.sleep(10)  # Check queue every 10 seconds
                
            except queue.Empty:
                time.sleep(10)
            except Exception as e:
                logger.error(f"❌ Error processing GIF queue: {e}")
                time.sleep(30)
    
    def monitor_mets_home_runs(self, keep_alive_url: Optional[str] = None):
        """Main monitoring loop"""
        logger.info("🏠⚾ Starting Mets Home Run Tracker - LET'S GO METS!")
        logger.info(f"🔗 Keep-alive URL: {keep_alive_url}")
        self.monitoring_active = True
        
        # Start GIF processing thread
        gif_thread = Thread(target=self.process_gif_queue, daemon=True)
        gif_thread.start()
        logger.info("🎬 Started GIF processing thread")
        
        cycle_count = 0
        
        try:
            while self.monitoring_active:
                try:
                    cycle_count += 1
                    logger.info(f"🔄 Starting monitoring cycle #{cycle_count}")
                    
                    # Get live Mets games
                    games = self.get_live_mets_games()
                    
                    if not games:
                        logger.info("📅 No Mets games found today - standing by...")
                    else:
                        logger.info(f"🎯 Found {len(games)} Mets game(s) to monitor")
                        
                        for game in games:
                            game_pk = game['gamePk']
                            plays = self.get_game_plays(game_pk)
                            
                            if not plays:
                                logger.info(f"📋 No plays found for game {game_pk}")
                                continue
                            
                            # Check each play for Mets home runs
                            new_hrs_found = 0
                            for play in plays:
                                home_run = self.is_mets_home_run(play, game_pk)
                                if home_run:
                                    # Add to processed set
                                    self.processed_plays.add(home_run.play_id)
                                    
                                    # Add to queue for processing
                                    self.home_run_queue.put(home_run)
                                    self.stats['homeruns_queued_today'] += 1
                                    new_hrs_found += 1
                                    
                                    logger.info(f"🎬 Queued {home_run.player_name} HR for processing!")
                            
                            if new_hrs_found == 0:
                                logger.info(f"🔍 Scanned {len(plays)} plays in game {game_pk} - no new Mets HRs")
                    
                    # Update statistics
                    self.stats['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.stats['processed_plays'] = len(self.processed_plays)
                    
                    # Save processed plays
                    self.save_processed_plays()
                    
                    # Log comprehensive status
                    uptime = str(datetime.now() - self.start_time).split('.')[0]
                    logger.info(f"📊 System Status - Uptime: {uptime}")
                    logger.info(f"📊 Today's Stats - HRs Posted: {self.stats['homeruns_posted_today']}, GIFs: {self.stats['gifs_created_today']}, Queue: {self.home_run_queue.qsize()}")
                    logger.info(f"📊 API Calls: {self.stats['api_calls_today']}, Errors: {self.stats['errors_today']}")
                    
                    # Keep-alive ping
                    if keep_alive_url:
                        try:
                            response = requests.get(keep_alive_url, timeout=5)
                            if response.status_code == 200:
                                logger.info("💓 Keep-alive ping successful")
                            else:
                                logger.warning(f"⚠️ Keep-alive ping returned status {response.status_code}")
                        except Exception as e:
                            logger.warning(f"⚠️ Keep-alive ping failed: {e}")
                    
                    # Wait before next check (2 minutes)
                    logger.info("⏰ Waiting 2 minutes before next check...")
                    time.sleep(120)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"💥 Error in monitoring loop: {e}")
                    self.stats['errors_today'] += 1
                    logger.info("⏰ Waiting 60 seconds before retry...")
                    time.sleep(60)  # Wait before retry
                    
        except KeyboardInterrupt:
            logger.info("👋 Monitoring stopped by user")
        finally:
            self.monitoring_active = False
            logger.info("🛑 Mets Home Run Tracker stopped")
    
    def stop_monitoring(self):
        """Stop the monitoring process"""
        self.monitoring_active = False
        logger.info("🛑 Stopping Mets Home Run Tracker...")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        uptime = str(datetime.now() - self.start_time).split('.')[0] if self.monitoring_active else None
        
        return {
            'monitoring': self.monitoring_active,
            'uptime': uptime,
            'last_check': self.stats.get('last_check'),
            'queue_size': self.home_run_queue.qsize(),
            'processed_plays': len(self.processed_plays),
            'stats': self.stats
        }

def main():
    """Main function"""
    tracker = MetsHomeRunTracker()
    
    try:
        tracker.monitor_mets_home_runs()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        tracker.stop_monitoring()

if __name__ == "__main__":
    main() 