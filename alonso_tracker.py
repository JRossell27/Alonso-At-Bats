import os
import time
import logging
import warnings
from datetime import datetime
import tweepy
from dotenv import load_dotenv
import requests
import random
import gc  # For garbage collection
from flask import Flask, render_template
import threading
from pathlib import Path
import json

# Import our GIF integration module
try:
    from baseball_savant_gif_integration import BaseballSavantGIFIntegration
    GIF_INTEGRATION_AVAILABLE = True
except ImportError:
    GIF_INTEGRATION_AVAILABLE = False
    logging.warning("GIF integration not available - install ffmpeg and ffmpeg-python for GIF support")

# Suppress SyntaxWarnings from tweepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Test mode flag
TEST_MODE = False  # Set to False for production - bot will now tweet real at-bats!

# Deployment test flag - sends one test tweet on startup
DEPLOYMENT_TEST = False  # Set to True to send a test tweet on startup, then set back to False

# Pete Alonso's MLB ID (hardcoded to avoid lookup issues)
ALONSO_MLB_ID = 624413

# Twitter API setup
if not TEST_MODE:
    try:
        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
            bearer_token=os.getenv('TWITTER_BEARER_TOKEN')
        )
        
        # Also set up the v1.1 API for media uploads and quote tweets
        auth = tweepy.OAuthHandler(
            os.getenv('TWITTER_API_KEY'),
            os.getenv('TWITTER_API_SECRET')
        )
        auth.set_access_token(
            os.getenv('TWITTER_ACCESS_TOKEN'),
            os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        )
        api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
        
        logger.info("Twitter clients initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twitter clients: {str(e)}")
        api_v1 = None

# Keep track of processed at-bats and their tweet IDs for GIF follow-ups
processed_at_bats = set()
tweet_gif_queue = []  # Store (tweet_id, play_data) for GIF processing

# Persistence file for processed at-bats
PROCESSED_AT_BATS_FILE = "processed_at_bats.json"

def load_processed_at_bats():
    """Load processed at-bats from file to prevent duplicates after restart"""
    global processed_at_bats
    try:
        if Path(PROCESSED_AT_BATS_FILE).exists():
            with open(PROCESSED_AT_BATS_FILE, 'r') as f:
                data = json.load(f)
                processed_at_bats = set(data.get('at_bats', []))
                logger.info(f"Loaded {len(processed_at_bats)} processed at-bats from file")
        else:
            logger.info("No processed at-bats file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading processed at-bats: {str(e)}")
        processed_at_bats = set()

def save_processed_at_bats():
    """Save processed at-bats to file for persistence"""
    try:
        data = {
            'at_bats': list(processed_at_bats),
            'last_updated': datetime.now().isoformat(),
            'count': len(processed_at_bats)
        }
        with open(PROCESSED_AT_BATS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved {len(processed_at_bats)} processed at-bats to file")
    except Exception as e:
        logger.error(f"Error saving processed at-bats: {str(e)}")

def cleanup_old_at_bats():
    """Remove at-bats older than 7 days to prevent memory bloat"""
    global processed_at_bats
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        old_at_bats = []
        
        for at_bat_id in processed_at_bats:
            # Extract date from at_bat_id (format: game_id_inning_play_id_date)
            parts = at_bat_id.split('_')
            if len(parts) >= 4:
                at_bat_date = parts[-1]  # Last part should be the date
                try:
                    at_bat_datetime = datetime.strptime(at_bat_date, '%Y-%m-%d')
                    days_old = (datetime.now() - at_bat_datetime).days
                    if days_old > 7:
                        old_at_bats.append(at_bat_id)
                except ValueError:
                    # If date parsing fails, keep the at-bat to be safe
                    continue
        
        # Remove old at-bats
        for old_at_bat in old_at_bats:
            processed_at_bats.discard(old_at_bat)
        
        if old_at_bats:
            logger.info(f"Cleaned up {len(old_at_bats)} old at-bats (>7 days)")
            save_processed_at_bats()
            
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

# Track last check time and status
last_check_time = None
last_check_status = "Initializing..."

# Cache for season stats to avoid repeated API calls
season_stats_cache = {}
cache_timestamp = None

# Initialize GIF integration if available
if GIF_INTEGRATION_AVAILABLE:
    gif_integration = BaseballSavantGIFIntegration()
    logger.info("GIF integration initialized")
else:
    gif_integration = None

def get_alonso_id():
    """Get Pete Alonso's MLB ID (hardcoded for reliability)"""
    return ALONSO_MLB_ID

def get_current_games():
    """Get all current games for today with live data"""
    try:
        url = "https://statsapi.mlb.com/api/v1/schedule"
        params = {
            "sportId": 1,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "hydrate": "game(content(editorial(recap))),linescore,team,probablePitcher,decisions"
        }
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching current games: {str(e)}")
        return {}

def get_live_game_data(game_id):
    """Get live play-by-play data for a specific game"""
    try:
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
        response = requests.get(url, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching live game data for {game_id}: {str(e)}")
        return {}

def find_alonso_games_today():
    """Find games where Pete Alonso is playing today"""
    games_data = get_current_games()
    alonso_games = []
    
    if not games_data.get('dates'):
        return alonso_games
    
    for date_data in games_data['dates']:
        for game in date_data.get('games', []):
            game_id = game.get('gamePk')
            if not game_id:
                continue
                
            # Check if Mets are playing (Pete Alonso's team)
            home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('abbreviation', '')
            away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('abbreviation', '')
            
            if 'NYM' in [home_team, away_team]:
                alonso_games.append({
                    'game_id': game_id,
                    'home_team': home_team,
                    'away_team': away_team,
                    'game_state': game.get('status', {}).get('detailedState', ''),
                    'inning': game.get('linescore', {}).get('currentInning', 1),
                    'inning_state': game.get('linescore', {}).get('inningState', ''),
                    'is_live': game.get('status', {}).get('statusCode') in ['I', 'IR', 'IH']  # In progress states
                })
                logger.info(f"Found Mets game: {away_team} @ {home_team} (Game ID: {game_id}, State: {game.get('status', {}).get('detailedState', '')})")
    
    return alonso_games

def extract_alonso_at_bats_from_live_data(live_data):
    """Extract Pete Alonso's at-bats from live game data"""
    at_bats = []
    
    if not live_data.get('liveData', {}).get('plays', {}).get('allPlays'):
        return at_bats
    
    all_plays = live_data['liveData']['plays']['allPlays']
    
    for play in all_plays:
        # Check if Pete Alonso is the batter
        batter_id = play.get('matchup', {}).get('batter', {}).get('id')
        if batter_id == ALONSO_MLB_ID:
            # Extract detailed play information
            play_id = play.get('atBatIndex', 0)
            inning = play.get('about', {}).get('inning', 1)
            game_id = live_data.get('gamePk', 0)
            
            # Create unique ID for this at-bat
            at_bat_id = f"{game_id}_{inning}_{play_id}_{datetime.now().strftime('%Y-%m-%d')}"
            
            # Extract result and hit data
            result = play.get('result', {})
            hit_data = play.get('hitData', {})
            pitch_data = play.get('pitchData', {}) if play.get('pitchData') else {}
            
            # Get the last pitch for strikeout data
            last_pitch = None
            if play.get('playEvents'):
                for event in reversed(play['playEvents']):
                    if event.get('isPitch') and event.get('details'):
                        last_pitch = event
                        break
            
            at_bat_data = {
                'at_bat_id': at_bat_id,
                'game_id': game_id,
                'play_id': play_id,
                'inning': inning,
                'inning_half': play.get('about', {}).get('halfInning', 'top'),
                'description': result.get('description', 'Unknown'),
                'event': result.get('event', 'Unknown'),
                'rbi': result.get('rbi', 0),
                'runners_on_base': len(play.get('runners', [])),
                'outs': play.get('count', {}).get('outs', 0),
                'balls': play.get('count', {}).get('balls', 0),
                'strikes': play.get('count', {}).get('strikes', 0),
                'hit_data': {
                    'launch_speed': hit_data.get('launchSpeed'),
                    'launch_angle': hit_data.get('launchAngle'),
                    'total_distance': hit_data.get('totalDistance'),
                    'trajectory': hit_data.get('trajectory'),
                    'hardness': hit_data.get('hardness'),
                    'location': hit_data.get('location'),
                    'coord_x': hit_data.get('coordinates', {}).get('coordX'),
                    'coord_y': hit_data.get('coordinates', {}).get('coordY')
                },
                'pitch_data': {
                    'start_speed': last_pitch.get('pitchData', {}).get('startSpeed') if last_pitch else None,
                    'pitch_type': last_pitch.get('details', {}).get('type', {}).get('description') if last_pitch else None,
                    'zone': last_pitch.get('pitchData', {}).get('zone') if last_pitch else None
                },
                'game_situation': {
                    'home_score': live_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('home', {}).get('runs', 0),
                    'away_score': live_data.get('liveData', {}).get('linescore', {}).get('teams', {}).get('away', {}).get('runs', 0),
                    'inning_state': live_data.get('liveData', {}).get('linescore', {}).get('inningState', '')
                },
                'timestamp': datetime.now()
            }
            
            at_bats.append(at_bat_data)
    
    return at_bats

def get_alonso_season_stats():
    """Get Alonso's comprehensive season stats with caching"""
    global season_stats_cache, cache_timestamp
    
    # Check if cache is still valid (refresh every 10 minutes)
    if cache_timestamp and (datetime.now() - cache_timestamp).seconds < 600:
        return season_stats_cache
    
    alonso_id = get_alonso_id()
    if not alonso_id:
        return None
    
    try:
        # Get hitting stats
        url = f"https://statsapi.mlb.com/api/v1/people/{alonso_id}/stats"
        params = {
            "stats": "season",
            "season": datetime.now().year,
            "group": "hitting"
        }
        response = requests.get(url, params=params)
        hitting_data = response.json()
        
        # Get advanced stats
        params_advanced = {
            "stats": "season",
            "season": datetime.now().year,
            "group": "hitting",
            "statType": "advanced"
        }
        response_advanced = requests.get(url, params=params_advanced)
        advanced_data = response_advanced.json()
        
        # Parse and cache the stats
        stats = {}
        if hitting_data.get('stats') and len(hitting_data['stats']) > 0:
            hitting_stats = hitting_data['stats'][0]['splits'][0]['stat']
            stats.update({
                'avg': hitting_stats.get('avg', '.000'),
                'obp': hitting_stats.get('obp', '.000'),
                'slg': hitting_stats.get('slg', '.000'),
                'ops': hitting_stats.get('ops', '.000'),
                'homeRuns': hitting_stats.get('homeRuns', 0),
                'rbi': hitting_stats.get('rbi', 0),
                'runs': hitting_stats.get('runs', 0),
                'hits': hitting_stats.get('hits', 0),
                'doubles': hitting_stats.get('doubles', 0),
                'triples': hitting_stats.get('triples', 0),
                'walks': hitting_stats.get('baseOnBalls', 0),
                'strikeouts': hitting_stats.get('strikeOuts', 0),
                'stolenBases': hitting_stats.get('stolenBases', 0),
                'atBats': hitting_stats.get('atBats', 0),
                'plateAppearances': hitting_stats.get('plateAppearances', 0)
            })
        
        if advanced_data.get('stats') and len(advanced_data['stats']) > 0:
            advanced_stats = advanced_data['stats'][0]['splits'][0]['stat']
            stats.update({
                'wrc_plus': advanced_stats.get('wrcPlus', 'N/A'),
                'war': advanced_stats.get('war', 'N/A'),
                'babip': advanced_stats.get('babip', 'N/A'),
                'iso': advanced_stats.get('iso', 'N/A')
            })
        
        season_stats_cache = stats
        cache_timestamp = datetime.now()
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching season stats: {str(e)}")
        return season_stats_cache if season_stats_cache else {}

def get_situational_context():
    """Get situational context for the at-bat"""
    situations = [
        "with runners in scoring position",
        "with bases loaded",
        "with 2 outs",
        "in a clutch situation",
        "leading off the inning",
        "with a runner on first",
        "in the late innings",
        "against a lefty",
        "against a righty",
        "on a 3-2 count",
        "on the first pitch",
        "after falling behind 0-2"
    ]
    return random.choice(situations)

def calculate_ops(avg, obp, slg):
    """Calculate OPS from individual stats"""
    try:
        return round(float(obp) + float(slg), 3)
    except:
        return "N/A"

def format_tweet(play_data):
    """Format the tweet based on the play data with enhanced stats"""
    season_stats = get_alonso_season_stats()
    
    if play_data['type'] == 'home_run':
        # Enhanced home run tweet
        tweet = f"🚨 Pete Alonso GOES YARD! 🚨\n\n"
        tweet += f"💥 Exit Velocity: {play_data['exit_velocity']} mph\n"
        tweet += f"📏 Distance: {play_data['distance']} ft\n"
        tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        # Add barrel classification if available
        if play_data.get('barrel_classification'):
            tweet += f"🎯 {play_data['barrel_classification']}\n"
        
        # Season context
        if season_stats:
            new_hr_total = season_stats.get('homeRuns', 0) + 1
            tweet += f"\n🏆 Season HR #{new_hr_total}\n"
            tweet += f"📊 Season Stats: .{season_stats.get('avg', '000')}/{season_stats.get('obp', '.000')}/{season_stats.get('slg', '.000')}\n"
            tweet += f"💪 OPS: {season_stats.get('ops', 'N/A')}\n"
            
            if season_stats.get('rbi'):
                tweet += f"🏃 RBI: {season_stats.get('rbi', 0) + play_data.get('rbi_on_play', 1)}\n"
        
        # Situational context
        if play_data.get('situation'):
            tweet += f"⚾ {play_data['situation']}\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() in ['single', 'double', 'triple']:
        # Enhanced hit tweet
        hit_type = play_data['description'].upper()
        emoji = "💫" if hit_type == "SINGLE" else "⚡" if hit_type == "DOUBLE" else "🔥"
        
        tweet = f"{emoji} Pete Alonso with a {hit_type}!\n\n"
        
        # Hit data
        if play_data.get('exit_velocity') != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if play_data.get('launch_angle') != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        if play_data.get('hit_distance') != 'N/A':
            tweet += f"📏 Distance: {play_data['hit_distance']} ft\n"
        
        # Expected stats
        if play_data.get('xba'):
            tweet += f"📈 xBA: {play_data['xba']}\n"
        
        # Season context
        if season_stats:
            tweet += f"\n📊 Season: .{season_stats.get('avg', '000')} AVG, {season_stats.get('ops', 'N/A')} OPS\n"
            tweet += f"🏃 {season_stats.get('hits', 0) + 1} hits, {season_stats.get('rbi', 0)} RBI\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() == 'walk':
        tweet = f"👁️ Pete Alonso draws a WALK!\n\n"
        
        # Plate discipline stats
        if season_stats:
            walk_rate = round((season_stats.get('walks', 0) + 1) / season_stats.get('plateAppearances', 1) * 100, 1)
            tweet += f"🎯 Plate Discipline: {walk_rate}% BB rate\n"
            tweet += f"📊 Season: {season_stats.get('walks', 0) + 1} BB, {season_stats.get('strikeouts', 0)} K\n"
            tweet += f"👀 OBP: {season_stats.get('obp', '.000')}\n"
        
        # Situational context
        if play_data.get('situation'):
            tweet += f"⚾ {play_data['situation']}\n"
        
        tweet += f"\n#LGM"
        
    elif play_data['description'].lower() == 'strikeout':
        tweet = f"❌ Pete Alonso strikes out"
        
        # Add strikeout type
        if play_data.get('strikeout_type') != 'N/A':
            tweet += f" {play_data['strikeout_type']}"
        
        tweet += "\n\n"
        
        # Pitch details
        if play_data.get('pitch_type') != 'N/A':
            tweet += f"🎯 Final Pitch: {play_data['pitch_type']}\n"
        if play_data.get('pitch_speed') != 'N/A':
            tweet += f"⚡ Speed: {play_data['pitch_speed']} mph\n"
        if play_data.get('pitch_location') != 'N/A':
            tweet += f"📍 Location: {play_data['pitch_location']}\n"
        
        # Season strikeout context
        if season_stats:
            k_rate = round(season_stats.get('strikeouts', 0) / season_stats.get('plateAppearances', 1) * 100, 1)
            tweet += f"\n📊 Season K Rate: {k_rate}%\n"
            tweet += f"⚾ {season_stats.get('strikeouts', 0) + 1} K, {season_stats.get('walks', 0)} BB\n"
        
        tweet += f"\n#LGM"
        
    else:
        # Generic at-bat with enhanced context
        tweet = f"⚾ Pete Alonso: {play_data['description']}\n\n"
        
        # Add relevant stats if available
        if play_data.get('exit_velocity') != 'N/A':
            tweet += f"💪 Exit Velocity: {play_data['exit_velocity']} mph\n"
        if play_data.get('launch_angle') != 'N/A':
            tweet += f"📐 Launch Angle: {play_data['launch_angle']}°\n"
        
        # Season context
        if season_stats:
            tweet += f"\n📊 Season: .{season_stats.get('avg', '000')}/{season_stats.get('obp', '.000')}/{season_stats.get('slg', '.000')}\n"
        
        tweet += f"\n#LGM"
    
    return tweet

def keep_alive():
    """Enhanced keep-alive mechanism with better error handling"""
    try:
        # Try to ping our own service
        response = requests.get("https://alonso-at-bat-tracker.onrender.com/", timeout=5)
        if response.status_code == 200:
            logger.debug("Keep-alive ping successful")
        else:
            logger.warning(f"Keep-alive ping returned status {response.status_code}")
    except requests.exceptions.Timeout:
        logger.warning("Keep-alive ping timed out")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Keep-alive ping failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in keep-alive: {str(e)}")

def send_deployment_test_tweet():
    """Send a one-time test tweet on deployment"""
    try:
        test_tweet = f"""🚀 Pete Alonso Bot - Deployment Test

✅ Bot successfully deployed and running!
📅 Deployed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
⚾ Ready to track Pete Alonso's at-bats!

🤖 This is an automated deployment test
🗑️ Will be manually deleted

#LGM"""
        
        if not TEST_MODE:
            response = client.create_tweet(text=test_tweet)
            logger.info(f"🚀 DEPLOYMENT TEST TWEET SENT! Tweet ID: {response.data['id']}")
            logger.info(f"Tweet URL: https://twitter.com/user/status/{response.data['id']}")
            return True
        else:
            logger.info(f"TEST MODE - Would send deployment test tweet: {test_tweet}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send deployment test tweet: {str(e)}")
        return False

def generate_test_at_bat():
    """Generate a test at-bat with enhanced random data"""
    is_home_run = random.random() < 0.25  # 25% chance of home run
    
    if is_home_run:
        return {
            'events': 'home_run',
            'description': 'Home Run',
            'launch_speed': round(random.uniform(100, 118), 1),
            'launch_angle': round(random.uniform(22, 35), 1),
            'hit_distance_sc': round(random.uniform(380, 470)),
            'barrel': random.randint(25, 35),
            'home_run': random.randint(1, 35),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5),
            'barrel_classification': random.choice(['Barrel', 'Solid Contact', 'Hard Hit']),
            'xba': round(random.uniform(0.8, 1.0), 3),
            'situation': get_situational_context(),
            'rbi_on_play': random.randint(1, 4)
        }
    else:
        outcomes = ['Single', 'Double', 'Triple', 'Strikeout', 'Walk', 'Groundout', 'Flyout', 'Line Out']
        outcome = random.choice(outcomes)
        result = {
            'events': outcome.lower(),
            'description': outcome,
            'launch_speed': round(random.uniform(65, 115), 1),
            'launch_angle': round(random.uniform(-15, 45), 1),
            'game_date': datetime.now().strftime("%Y-%m-%d"),
            'inning': random.randint(1, 9),
            'at_bat_number': random.randint(1, 5),
            'situation': get_situational_context()
        }
        
        # Add hit-specific data
        if outcome in ['Single', 'Double', 'Triple']:
            result.update({
                'hit_distance': round(random.uniform(200, 350)),
                'xba': round(random.uniform(0.1, 0.9), 3),
                'rbi_on_play': random.randint(0, 2) if outcome != 'Triple' else random.randint(1, 3)
            })
        
        # Add strikeout-specific data
        elif outcome == 'Strikeout':
            result.update({
                'strikeout_type': random.choice(['looking', 'swinging']),
                'pitch_type': random.choice(['4-Seam Fastball', 'Slider', 'Curveball', 'Changeup', 'Cutter', 'Sinker', 'Knuckle Curve']),
                'pitch_speed': round(random.uniform(82, 101), 1),
                'pitch_location': random.choice(['High and Inside', 'Low and Away', 'Middle-In', 'Middle-Out', 'High and Away', 'Low and In', 'Up in the Zone'])
            })
        
        return result

def post_tweet_with_gif_followup(tweet_text, play_data, game_data=None):
    """Post immediate tweet and queue GIF follow-up"""
    try:
        # Post immediate tweet
        if not TEST_MODE and client:
            response = client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            logger.info(f"Immediate tweet posted: {tweet_id}")
            
            # Queue for GIF follow-up if available
            if gif_integration and game_data:
                tweet_gif_queue.append({
                    'tweet_id': tweet_id,
                    'play_data': play_data,
                    'game_data': game_data,
                    'timestamp': datetime.now()
                })
                logger.info(f"Queued for GIF follow-up: {tweet_id}")
            
            # Save processed at-bats after successful tweet
            save_processed_at_bats()
            
            return tweet_id
        else:
            logger.info(f"TEST MODE - Would tweet: {tweet_text}")
            if gif_integration and game_data:
                # Even in test mode, queue for GIF testing
                fake_tweet_id = f"test_{int(time.time())}"
                tweet_gif_queue.append({
                    'tweet_id': fake_tweet_id,
                    'play_data': play_data,
                    'game_data': game_data,
                    'timestamp': datetime.now()
                })
                logger.info(f"TEST MODE - Queued for GIF follow-up: {fake_tweet_id}")
            
            # Save processed at-bats even in test mode
            save_processed_at_bats()
            return None
            
    except Exception as e:
        logger.error(f"Error posting tweet: {str(e)}")
        return None

def create_gif_quote_tweet(original_tweet_id, play_data, game_data):
    """Create a quote tweet with just the GIF"""
    try:
        if not gif_integration:
            logger.warning("GIF integration not available")
            return False
            
        logger.info(f"Creating GIF for tweet {original_tweet_id}")
        
        # Extract relevant data for GIF creation
        game_id = game_data.get('game_id')
        play_id = play_data.get('play_id', 1)
        game_date = datetime.now().strftime('%Y-%m-%d')
        
        # Create MLB play data structure for GIF matching
        mlb_play_data = {
            'result': {
                'event': play_data.get('description', '')
            },
            'about': {
                'inning': play_data.get('inning', 1)
            },
            'matchup': {
                'batter': {
                    'id': 624413,  # Pete Alonso's ID
                    'fullName': 'Pete Alonso'
                }
            }
        }
        
        # Create the GIF
        gif_path = gif_integration.get_gif_for_play(
            game_id=game_id,
            play_id=play_id,
            game_date=game_date,
            mlb_play_data=mlb_play_data
        )
        
        if gif_path and Path(gif_path).exists():
            logger.info(f"GIF created successfully: {gif_path}")
            
            # Create quote tweet text - just the visual emoji and credit
            quote_text = f"🎬 Watch the play\n\nAnimation courtesy of @baseballsavant"
            
            if not TEST_MODE and api_v1:
                # Upload GIF
                media = api_v1.media_upload(gif_path)
                
                # Create quote tweet by replying to the original tweet with media
                quote_tweet = api_v1.update_status(
                    status=quote_text,
                    media_ids=[media.media_id],
                    in_reply_to_status_id=original_tweet_id,
                    auto_populate_reply_metadata=False  # Don't include @mentions
                )
                
                logger.info(f"🎬 GIF quote tweet posted: {quote_tweet.id}")
                
                # Clean up the GIF file
                Path(gif_path).unlink(missing_ok=True)
                logger.info(f"Cleaned up GIF file: {gif_path}")
                
                return True
            else:
                logger.info(f"TEST MODE - Would post GIF quote tweet for {original_tweet_id}")
                logger.info(f"GIF path: {gif_path}")
                logger.info(f"Quote text: {quote_text}")
                return True
                
        else:
            logger.info(f"⏳ GIF not yet available for tweet {original_tweet_id} - video may not be ready on Baseball Savant")
            return False
            
    except Exception as e:
        logger.error(f"Error creating GIF quote tweet for {original_tweet_id}: {str(e)}")
        return False

def process_gif_queue():
    """Background thread to process queued tweets for GIF creation"""
    logger.info("🎬 Starting GIF processing thread...")
    
    while True:
        try:
            # Process queued items
            items_to_remove = []
            
            for i, item in enumerate(tweet_gif_queue):
                tweet_id = item['tweet_id']
                play_data = item['play_data']
                game_data = item['game_data']
                timestamp = item['timestamp']
                
                # Track retry attempts and timing
                if 'attempts' not in item:
                    item['attempts'] = 0
                    item['last_attempt'] = None
                
                # Calculate time since original at-bat
                time_since_at_bat = (datetime.now() - timestamp).total_seconds()
                
                # Give up after 30 minutes of trying
                if time_since_at_bat > 1800:  # 30 minutes
                    logger.warning(f"❌ Giving up on GIF for tweet {tweet_id} after 30 minutes")
                    items_to_remove.append(i)
                    continue
                
                # Exponential backoff for retry attempts
                # Start checking after 30 seconds, then 1 min, 2 min, 4 min, 8 min, etc.
                if item['attempts'] == 0:
                    wait_time = 30  # First attempt after 30 seconds
                else:
                    wait_time = min(60 * (2 ** (item['attempts'] - 1)), 600)  # Max 10 minutes between attempts
                
                # Check if enough time has passed since last attempt
                if item['last_attempt']:
                    time_since_last_attempt = (datetime.now() - item['last_attempt']).total_seconds()
                    if time_since_last_attempt < wait_time:
                        continue
                else:
                    # First attempt - wait initial period
                    if time_since_at_bat < 30:
                        continue
                
                # Attempt to create GIF
                item['attempts'] += 1
                item['last_attempt'] = datetime.now()
                
                logger.info(f"🎬 Attempting to create GIF for tweet {tweet_id} (attempt {item['attempts']}, {time_since_at_bat:.0f}s after at-bat)")
                
                try:
                    # Try to create GIF quote tweet
                    success = create_gif_quote_tweet(tweet_id, play_data, game_data)
                    
                    if success:
                        logger.info(f"✅ GIF quote tweet completed for {tweet_id} after {item['attempts']} attempts")
                        items_to_remove.append(i)
                    else:
                        logger.info(f"⏳ GIF not yet available for tweet {tweet_id}, will retry in {wait_time}s (attempt {item['attempts']})")
                        
                        # Give up after 10 attempts
                        if item['attempts'] >= 10:
                            logger.warning(f"❌ Giving up on GIF for tweet {tweet_id} after {item['attempts']} attempts")
                            items_to_remove.append(i)
                
                except Exception as e:
                    logger.error(f"Error creating GIF for tweet {tweet_id} (attempt {item['attempts']}): {str(e)}")
                    
                    # Give up after 10 attempts
                    if item['attempts'] >= 10:
                        logger.warning(f"❌ Giving up on GIF for tweet {tweet_id} after {item['attempts']} attempts due to errors")
                        items_to_remove.append(i)
            
            # Remove processed/failed items (in reverse order to maintain indices)
            for i in reversed(items_to_remove):
                removed_item = tweet_gif_queue.pop(i)
                logger.debug(f"Removed tweet {removed_item['tweet_id']} from GIF queue")
            
            # Sleep before next check - check more frequently
            time.sleep(15)  # Check every 15 seconds for more responsive monitoring
            
        except Exception as e:
            logger.error(f"Error in GIF processing thread: {str(e)}")
            time.sleep(60)

def check_alonso_at_bats():
    """Enhanced at-bat checking with live game data"""
    global last_check_time, last_check_status
    
    try:
        logger.info("🔍 Checking for Pete Alonso at-bats...")
        
        if TEST_MODE:
            # Keep existing test mode logic
            test_at_bat = generate_test_at_bat()
            at_bat_id = f"{test_at_bat['game_date']}_{test_at_bat['inning']}_{test_at_bat['at_bat_number']}"
            
            logger.info(f"Generated test at-bat: {test_at_bat['description']} (ID: {at_bat_id})")
            
            if at_bat_id not in processed_at_bats:
                logger.info(f"New at-bat found! Processing: {test_at_bat['description']}")
                
                play_data = {
                    'type': 'home_run' if test_at_bat['events'] == 'home_run' else 'other',
                    'description': test_at_bat['description'],
                    'exit_velocity': test_at_bat.get('launch_speed', 'N/A'),
                    'launch_angle': test_at_bat.get('launch_angle', 'N/A'),
                    'distance': test_at_bat.get('hit_distance_sc', 'N/A'),
                    'parks': test_at_bat.get('barrel', 'N/A'),
                    'hr_number': test_at_bat.get('home_run', 0),
                    'situation': test_at_bat.get('situation', ''),
                    'barrel_classification': test_at_bat.get('barrel_classification', ''),
                    'xba': test_at_bat.get('xba', 'N/A'),
                    'hit_distance': test_at_bat.get('hit_distance', 'N/A'),
                    'rbi_on_play': test_at_bat.get('rbi_on_play', 0),
                    'play_id': test_at_bat.get('at_bat_number', 1),
                    'inning': test_at_bat.get('inning', 1)
                }
                
                # Add strikeout data if it's a strikeout
                if test_at_bat['events'] == 'strikeout':
                    play_data.update({
                        'strikeout_type': test_at_bat.get('strikeout_type', 'N/A'),
                        'pitch_type': test_at_bat.get('pitch_type', 'N/A'),
                        'pitch_speed': test_at_bat.get('pitch_speed', 'N/A'),
                        'pitch_location': test_at_bat.get('pitch_location', 'N/A')
                    })
                
                # Create fake game data for testing
                game_data = {
                    'game_id': 12345,  # Fake game ID for testing
                    'home_team': 'NYM',
                    'away_team': 'ATL'
                }
                
                tweet = format_tweet(play_data)
                
                # Post tweet with GIF follow-up
                tweet_id = post_tweet_with_gif_followup(tweet, play_data, game_data)
                
                processed_at_bats.add(at_bat_id)
                last_check_status = f"Found test at-bat: {test_at_bat['description']} {test_at_bat.get('situation', '')}"
                logger.info(f"At-bat processed and added to cache. Total processed: {len(processed_at_bats)}")
            else:
                logger.info(f"At-bat already processed (ID: {at_bat_id}). Skipping...")
                last_check_status = f"Duplicate at-bat skipped: {test_at_bat['description']}"
        else:
            # Production mode - use live game data
            alonso_games = find_alonso_games_today()
            
            if not alonso_games:
                last_check_status = "No Mets games found today"
                logger.info("No Mets games scheduled for today")
                return
            
            new_at_bats_found = 0
            
            for game_info in alonso_games:
                game_id = game_info['game_id']
                logger.info(f"📊 Checking game {game_id}: {game_info['away_team']} @ {game_info['home_team']} ({game_info['game_state']})")
                
                # Get live game data
                live_data = get_live_game_data(game_id)
                if not live_data:
                    logger.warning(f"Could not fetch live data for game {game_id}")
                    continue
                
                # Extract Alonso's at-bats from this game
                at_bats = extract_alonso_at_bats_from_live_data(live_data)
                
                for at_bat_data in at_bats:
                    at_bat_id = at_bat_data['at_bat_id']
                    
                    if at_bat_id not in processed_at_bats:
                        logger.info(f"🆕 NEW AT-BAT FOUND! {at_bat_data['event']} in inning {at_bat_data['inning']}")
                        new_at_bats_found += 1
                        
                        # Convert to our play_data format
                        play_data = {
                            'type': 'home_run' if at_bat_data['event'] == 'Home Run' else 'other',
                            'description': at_bat_data['event'],
                            'exit_velocity': at_bat_data['hit_data']['launch_speed'],
                            'launch_angle': at_bat_data['hit_data']['launch_angle'],
                            'distance': at_bat_data['hit_data']['total_distance'],
                            'hit_distance': at_bat_data['hit_data']['total_distance'],
                            'trajectory': at_bat_data['hit_data']['trajectory'],
                            'hardness': at_bat_data['hit_data']['hardness'],
                            'situation': f"in the {at_bat_data['inning_half']} of the {at_bat_data['inning']}{'st' if at_bat_data['inning'] == 1 else 'nd' if at_bat_data['inning'] == 2 else 'rd' if at_bat_data['inning'] == 3 else 'th'}",
                            'rbi_on_play': at_bat_data['rbi'],
                            'play_id': at_bat_data['play_id'],
                            'inning': at_bat_data['inning'],
                            'runners_on_base': at_bat_data['runners_on_base'],
                            'outs': at_bat_data['outs'],
                            'count': f"{at_bat_data['balls']}-{at_bat_data['strikes']}",
                            'game_situation': at_bat_data['game_situation']
                        }
                        
                        # Add strikeout-specific data
                        if at_bat_data['event'] == 'Strikeout':
                            play_data.update({
                                'strikeout_type': 'looking' if 'called' in at_bat_data['description'].lower() else 'swinging',
                                'pitch_type': at_bat_data['pitch_data']['pitch_type'],
                                'pitch_speed': at_bat_data['pitch_data']['start_speed'],
                                'pitch_zone': at_bat_data['pitch_data']['zone']
                            })
                        
                        # Game data for GIF creation
                        game_data = {
                            'game_id': game_id,
                            'home_team': game_info['home_team'],
                            'away_team': game_info['away_team']
                        }
                        
                        # Format and post tweet
                        tweet = format_tweet(play_data)
                        tweet_id = post_tweet_with_gif_followup(tweet, play_data, game_data)
                        
                        # Mark as processed
                        processed_at_bats.add(at_bat_id)
                        
                        logger.info(f"✅ At-bat processed and tweeted! Total processed: {len(processed_at_bats)}")
                    else:
                        logger.debug(f"At-bat {at_bat_id} already processed, skipping")
            
            if new_at_bats_found > 0:
                last_check_status = f"Found {new_at_bats_found} new at-bat(s)"
            else:
                last_check_status = "No new at-bats found"
                logger.info("No new at-bats found")
            
            # Clear memory after processing
            gc.collect()
        
        last_check_time = datetime.now()
        logger.info(f"✓ Check completed. Status: {last_check_status}")
        
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}"
        logger.error(error_msg, exc_info=True)
        last_check_status = error_msg

def background_checker():
    """Enhanced background checker with more frequent monitoring and better keep-alive"""
    logger.info("🚀 Starting enhanced background checker...")
    check_count = 0
    cleanup_count = 0
    
    while True:
        try:
            # Check for at-bats
            check_alonso_at_bats()
            check_count += 1
            
            # Keep alive every check (every 60 seconds)
            keep_alive()
            
            # Cleanup old at-bats every 100 checks (~100 minutes)
            cleanup_count += 1
            if cleanup_count >= 100:
                cleanup_old_at_bats()
                cleanup_count = 0
            
            # Log status every 10 checks (10 minutes)
            if check_count % 10 == 0:
                logger.info(f"📈 Background checker running: {check_count} checks completed, {len(processed_at_bats)} at-bats processed")
            
            # Sleep for 60 seconds (more frequent checking)
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in background checker: {str(e)}", exc_info=True)
            # Continue running even if there's an error
            time.sleep(60)

@app.route('/')
def home():
    """Render the home page with enhanced status information"""
    global last_check_time, last_check_status
    
    if last_check_time is None:
        status = "Initializing..."
        time_since_check = "N/A"
    else:
        status = f"Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')} UTC - {last_check_status}"
        time_diff = datetime.now() - last_check_time
        time_since_check = f"{int(time_diff.total_seconds())} seconds ago"
    
    # Get current season stats
    season_stats = get_alonso_season_stats()
    
    return f"""
    <html>
        <head>
            <title>Pete Alonso At-Bat Tracker</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 1000px;
                    margin: 0 auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                .container {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }}
                h1 {{
                    color: #002D72;
                    text-align: center;
                    margin-bottom: 10px;
                    font-size: 2.5em;
                }}
                .subtitle {{
                    text-align: center;
                    color: #666;
                    margin-bottom: 30px;
                    font-style: italic;
                }}
                .status-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .status-card {{
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 10px;
                    border-left: 5px solid #002D72;
                }}
                .status-card h3 {{
                    margin-top: 0;
                    color: #002D72;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-top: 20px;
                }}
                .stat-item {{
                    text-align: center;
                    padding: 15px;
                    background-color: #e9ecef;
                    border-radius: 8px;
                }}
                .stat-value {{
                    font-size: 1.8em;
                    font-weight: bold;
                    color: #002D72;
                }}
                .stat-label {{
                    font-size: 0.9em;
                    color: #666;
                    margin-top: 5px;
                }}
                .live-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    background-color: #28a745;
                    border-radius: 50%;
                    margin-right: 8px;
                    animation: pulse 2s infinite;
                }}
                @keyframes pulse {{
                    0% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                    100% {{ opacity: 1; }}
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #666;
                    font-size: 0.9em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚾ Pete Alonso At-Bat Tracker</h1>
                <div class="subtitle">Real-time monitoring with enhanced live game data</div>
                
                <div class="status-grid">
                    <div class="status-card">
                        <h3><span class="live-indicator"></span>System Status</h3>
                        <p><strong>Mode:</strong> {'🧪 TEST' if TEST_MODE else '🚀 PRODUCTION'}</p>
                        <p><strong>Status:</strong> {status}</p>
                        <p><strong>Last Check:</strong> {time_since_check}</p>
                        <p><strong>At-Bats Processed:</strong> {len(processed_at_bats)}</p>
                        <p><strong>GIF Integration:</strong> {'✅ Available' if GIF_INTEGRATION_AVAILABLE else '❌ Not Available'}</p>
                    </div>
                    
                    <div class="status-card">
                        <h3>📊 Season Stats</h3>
                        <p><strong>Average:</strong> {season_stats.get('avg', 'N/A')}</p>
                        <p><strong>Home Runs:</strong> {season_stats.get('homeRuns', 'N/A')}</p>
                        <p><strong>RBI:</strong> {season_stats.get('rbi', 'N/A')}</p>
                        <p><strong>OPS:</strong> {season_stats.get('ops', 'N/A')}</p>
                        <p><strong>At-Bats:</strong> {season_stats.get('atBats', 'N/A')}</p>
                    </div>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('homeRuns', 0)}</div>
                        <div class="stat-label">Home Runs</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('rbi', 0)}</div>
                        <div class="stat-label">RBI</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('avg', '.000')}</div>
                        <div class="stat-label">Batting Average</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('ops', '.000')}</div>
                        <div class="stat-label">OPS</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('runs', 0)}</div>
                        <div class="stat-label">Runs</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{season_stats.get('hits', 0)}</div>
                        <div class="stat-label">Hits</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>🔄 Page auto-refreshes every 30 seconds</p>
                    <p>⚡ Enhanced with live game data and improved monitoring</p>
                    <p>🤖 Automated Pete Alonso at-bat tracking for the New York Mets</p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring services"""
    global last_check_time, last_check_status
    
    # Determine health status
    if last_check_time is None:
        health_status = "starting"
        is_healthy = True
    else:
        time_since_check = (datetime.now() - last_check_time).total_seconds()
        if time_since_check > 300:  # More than 5 minutes
            health_status = "stale"
            is_healthy = False
        elif "Error" in last_check_status:
            health_status = "error"
            is_healthy = False
        else:
            health_status = "healthy"
            is_healthy = True
    
    response_data = {
        "status": health_status,
        "healthy": is_healthy,
        "last_check": last_check_time.isoformat() if last_check_time else None,
        "last_status": last_check_status,
        "processed_at_bats": len(processed_at_bats),
        "test_mode": TEST_MODE,
        "gif_integration": GIF_INTEGRATION_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
    
    status_code = 200 if is_healthy else 503
    return response_data, status_code

@app.route('/api/stats')
def api_stats():
    """API endpoint for current stats"""
    season_stats = get_alonso_season_stats()
    return {
        "player": "Pete Alonso",
        "mlb_id": ALONSO_MLB_ID,
        "season_stats": season_stats,
        "processed_at_bats": len(processed_at_bats),
        "last_check": last_check_time.isoformat() if last_check_time else None,
        "status": last_check_status
    }

if __name__ == "__main__":
    logger.info("Starting Pete Alonso At-Bat Tracker...")
    logger.info(f"TEST_MODE: {TEST_MODE}")
    logger.info(f"DEPLOYMENT_TEST: {DEPLOYMENT_TEST}")
    logger.info(f"ALONSO_MLB_ID: {ALONSO_MLB_ID}")
    logger.info(f"GIF Integration: {'Available' if GIF_INTEGRATION_AVAILABLE else 'Not Available'}")
    
    # Load processed at-bats from file
    logger.info("Loading processed at-bats from file...")
    load_processed_at_bats()
    
    # Send deployment test tweet if enabled
    if DEPLOYMENT_TEST and not TEST_MODE:
        logger.info("🚀 Sending deployment test tweet...")
        if send_deployment_test_tweet():
            logger.info("✅ Deployment test tweet sent successfully!")
        else:
            logger.error("❌ Failed to send deployment test tweet")
    elif DEPLOYMENT_TEST and TEST_MODE:
        logger.info("⚠️ DEPLOYMENT_TEST enabled but in TEST_MODE - no tweet will be sent")
    
    # Start the GIF processing thread if available
    if GIF_INTEGRATION_AVAILABLE:
        logger.info("Starting GIF processing thread...")
        try:
            gif_thread = threading.Thread(target=process_gif_queue, daemon=True)
            gif_thread.start()
            logger.info("✅ GIF processing thread started")
        except Exception as e:
            logger.error(f"❌ Failed to start GIF processing thread: {str(e)}")
    
    # Start the background checker thread
    logger.info("Starting background checker thread...")
    try:
        checker_thread = threading.Thread(target=background_checker, daemon=True)
        checker_thread.start()
        logger.info("✅ Background checker thread started")
    except Exception as e:
        logger.error(f"❌ Failed to start background checker thread: {str(e)}")
        # This is critical, so we should exit if we can't start the checker
        exit(1)
    
    # Start the Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}...")
    logger.info("🎯 Enhanced monitoring system active:")
    logger.info("   • Live game data monitoring")
    logger.info("   • 60-second check intervals")
    logger.info("   • Persistent at-bat tracking")
    logger.info("   • Enhanced keep-alive mechanism")
    logger.info("   • Health check endpoints")
    
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"❌ Flask app failed to start: {str(e)}")
        exit(1) 