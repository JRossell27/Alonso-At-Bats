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

def get_current_game():
    """Get the current game ID if Alonso is playing"""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": datetime.now().strftime("%m/%d/%Y")
    }
    response = requests.get(url, params=params)
    return response.json()

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
    """Send a request to keep the service alive"""
    try:
        requests.get("https://alonso-at-bat-tracker.onrender.com/")
    except:
        pass

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
    """Check for Alonso's at-bats and tweet if found"""
    global last_check_time, last_check_status
    
    try:
        alonso_id = get_alonso_id()
        logger.info("Checking for Alonso at-bats...")
        
        if TEST_MODE:
            # Generate test at-bat with enhanced data
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
            # Get current game data
            game_data_response = get_current_game()
            
            # Get Alonso's recent at-bats with enhanced data
            url = f"https://statsapi.mlb.com/api/v1/people/{alonso_id}/stats"
            params = {
                "stats": "gameLog",
                "season": datetime.now().year,
                "group": "hitting"
            }
            response = requests.get(url, params=params)
            recent_at_bats = response.json()
            
            # Also get live game data if available
            live_game_url = "https://statsapi.mlb.com/api/v1/schedule"
            live_params = {
                "sportId": 1,
                "date": datetime.now().strftime("%m/%d/%Y"),
                "hydrate": "game(content(editorial(recap))),linescore,team"
            }
            live_response = requests.get(live_game_url, params=live_params)
            live_data = live_response.json()
            
            logger.info("Checking MLB API for recent at-bats...")
            
            if recent_at_bats and 'stats' in recent_at_bats:
                for game in recent_at_bats['stats']:
                    if game.get('date') == datetime.now().strftime("%Y-%m-%d"):
                        for at_bat in game.get('splits', []):
                            at_bat_id = f"{game.get('date', 'unknown')}_{at_bat.get('inning', 1)}_{at_bat.get('atBatIndex', 1)}"
                            
                            if at_bat_id not in processed_at_bats:
                                logger.info(f"New MLB at-bat found! Processing...")
                                
                                # Enhanced play data extraction
                                result_event = at_bat.get('result', {}).get('event', 'Unknown')
                                hit_data = at_bat.get('hitData', {})
                                pitch_data = at_bat.get('pitchData', {})
                                
                                play_data = {
                                    'type': 'home_run' if result_event == 'Home Run' else 'other',
                                    'description': result_event,
                                    'exit_velocity': hit_data.get('launchSpeed', 'N/A'),
                                    'launch_angle': hit_data.get('launchAngle', 'N/A'),
                                    'distance': hit_data.get('totalDistance', 'N/A'),
                                    'hit_distance': hit_data.get('totalDistance', 'N/A'),
                                    'xba': hit_data.get('xba', 'N/A'),
                                    'barrel_classification': 'Barrel' if hit_data.get('isBarrel') else 'Hard Hit' if hit_data.get('launchSpeed', 0) > 95 else '',
                                    'situation': get_situational_context(),  # Could be enhanced with real game situation
                                    'rbi_on_play': at_bat.get('result', {}).get('rbi', 0),
                                    'play_id': at_bat.get('atBatIndex', 1),
                                    'inning': at_bat.get('inning', 1)
                                }
                                
                                # Add strikeout data if it's a strikeout
                                if result_event == 'Strikeout':
                                    play_data.update({
                                        'strikeout_type': 'looking' if 'called' in at_bat.get('result', {}).get('description', '').lower() else 'swinging',
                                        'pitch_type': pitch_data.get('type', 'N/A'),
                                        'pitch_speed': pitch_data.get('startSpeed', 'N/A'),
                                        'pitch_location': f"Zone {pitch_data.get('zone', 'N/A')}" if pitch_data.get('zone') else 'N/A'
                                    })
                                
                                # Extract game data for GIF creation
                                game_data = None
                                if live_data and 'dates' in live_data:
                                    for date_data in live_data['dates']:
                                        for live_game in date_data.get('games', []):
                                            # Try to match with current game
                                            game_data = {
                                                'game_id': live_game.get('gamePk'),
                                                'home_team': live_game.get('teams', {}).get('home', {}).get('team', {}).get('abbreviation', ''),
                                                'away_team': live_game.get('teams', {}).get('away', {}).get('team', {}).get('abbreviation', '')
                                            }
                                            break
                                
                                tweet = format_tweet(play_data)
                                
                                # Post tweet with GIF follow-up
                                tweet_id = post_tweet_with_gif_followup(tweet, play_data, game_data)
                                
                                processed_at_bats.add(at_bat_id)
                                last_check_status = f"Found at-bat: {result_event} {play_data.get('situation', '')}"
                                logger.info(f"MLB at-bat processed and tweeted. Total processed: {len(processed_at_bats)}")
                            else:
                                logger.info(f"MLB at-bat already processed (ID: {at_bat_id}). Skipping...")
            
            # Clear memory after processing
            gc.collect()
            
            if not last_check_status.startswith("Found") and not last_check_status.startswith("Duplicate"):
                last_check_status = "No new at-bats found"
                logger.info("No new at-bats found in MLB API")
        
        last_check_time = datetime.now()
        logger.info(f"Check completed. Status: {last_check_status}")
        
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}"
        logger.error(error_msg)
        last_check_status = error_msg

def background_checker():
    """Background thread to check for Alonso's at-bats"""
    while True:
        check_alonso_at_bats()
        # Keep the service alive to prevent spin-down
        keep_alive()
        time.sleep(120)  # Wait 2 minutes between checks

@app.route('/')
def home():
    """Render the home page with status information"""
    global last_check_time, last_check_status
    
    if last_check_time is None:
        status = "Initializing..."
    else:
        status = f"Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')} - {last_check_status}"
    
    return f"""
    <html>
        <head>
            <title>Pete Alonso HR Tracker</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #002D72;
                    text-align: center;
                }}
                .status {{
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    border-left: 5px solid #002D72;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Pete Alonso HR Tracker</h1>
                <div class="status">
                    <p><strong>Status:</strong> {status}</p>
                    <p><strong>Mode:</strong> {'TEST' if TEST_MODE else 'PRODUCTION'}</p>
                </div>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    logger.info("Starting Pete Alonso HR Tracker...")
    logger.info(f"TEST_MODE: {TEST_MODE}")
    logger.info(f"DEPLOYMENT_TEST: {DEPLOYMENT_TEST}")
    logger.info(f"ALONSO_MLB_ID: {ALONSO_MLB_ID}")
    logger.info(f"GIF Integration: {'Available' if GIF_INTEGRATION_AVAILABLE else 'Not Available'}")
    
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
        gif_thread = threading.Thread(target=process_gif_queue, daemon=True)
        gif_thread.start()
        logger.info("GIF processing thread started")
    
    # Start the background checker thread
    logger.info("Starting background checker thread...")
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()
    logger.info("Background checker thread started")
    
    # Start the Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}...")
    app.run(host='0.0.0.0', port=port) 