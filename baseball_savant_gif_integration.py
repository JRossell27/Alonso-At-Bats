#!/usr/bin/env python3
"""
Baseball Savant GIF Integration Module for Pete Alonso Tracker
Fetches Baseball Savant animations and converts them to GIFs for social media posts
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import subprocess
import tempfile
from pathlib import Path
import csv
from io import StringIO
import re

logger = logging.getLogger(__name__)

class BaseballSavantGIFIntegration:
    def __init__(self):
        self.savant_base = "https://baseballsavant.mlb.com"
        self.temp_dir = Path(tempfile.gettempdir()) / "alonso_gifs"
        self.temp_dir.mkdir(exist_ok=True)
        
    def get_statcast_data_for_play(self, game_id: int, play_id: int, game_date: str, mlb_play_data: Dict = None) -> Optional[Dict]:
        """Get Statcast data for a specific play"""
        try:
            params = {
                'all': 'true',
                'hfPT': '',
                'hfAB': '',
                'hfBBT': '',
                'hfPR': '',
                'hfZ': '',
                'stadium': '',
                'hfBBL': '',
                'hfNewZones': '',
                'hfGT': 'R|',  # Regular season
                'hfC': '',
                'hfSea': '2025|',  # Current season
                'hfSit': '',
                'player_type': 'batter',
                'hfOuts': '',
                'opponent': '',
                'pitcher_throws': '',
                'batter_stands': '',
                'hfSA': '',
                'game_date_gt': game_date,
                'game_date_lt': game_date,
                'hfInfield': '',
                'team': '',
                'position': '',
                'hfOutfield': '',
                'hfRO': '',
                'home_road': '',
                'game_pk': game_id,
                'hfFlag': '',
                'hfPull': '',
                'metric_1': '',
                'hfInn': '',
                'min_pitches': '0',
                'min_results': '0',
                'group_by': 'name',
                'sort_col': 'pitches',
                'player_event_sort': 'h_launch_speed',
                'sort_order': 'desc',
                'min_pas': '0',
                'type': 'details',
            }
            
            # Use the CSV export endpoint for easier parsing
            url = f"{self.savant_base}/statcast_search/csv"
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse CSV data
            csv_reader = csv.DictReader(StringIO(response.text))
            
            # Get all plays with events (not just pitches)
            plays_with_events = []
            for row in csv_reader:
                if row.get('events'):  # Only rows with actual events
                    plays_with_events.append(row)
            
            logger.info(f"Found {len(plays_with_events)} plays with events for game {game_id}")
            
            # If we have MLB play data to match against, try to find the exact play
            if mlb_play_data:
                target_event = mlb_play_data.get('result', {}).get('event', '').lower()
                target_inning = mlb_play_data.get('about', {}).get('inning')
                target_batter = mlb_play_data.get('matchup', {}).get('batter', {}).get('id')
                
                logger.info(f"Looking for Pete Alonso play: {target_event} in inning {target_inning}")
                
                # Try to find exact match
                for play in plays_with_events:
                    event = play.get('events', '').lower()
                    inning = play.get('inning')
                    batter_id = play.get('batter')
                    
                    # Match by event type, inning, and player ID (624413 for Pete Alonso)
                    if (target_event in event or event in target_event) and str(inning) == str(target_inning) and str(batter_id) == '624413':
                        logger.info(f"Found matching Alonso play: {event} in inning {inning}")
                        return play
                
                # If no exact match, try just by event type and player
                for play in plays_with_events:
                    event = play.get('events', '').lower()
                    batter_id = play.get('batter')
                    if (target_event in event or event in target_event) and str(batter_id) == '624413':
                        logger.info(f"Found Alonso play by event type: {event}")
                        return play
            
            # Fallback: look for any Pete Alonso play with events
            for play in plays_with_events:
                batter_id = play.get('batter')
                if str(batter_id) == '624413':  # Pete Alonso's ID
                    event = play.get('events', '').lower()
                    logger.info(f"Found Alonso play: {event}")
                    return play
            
            logger.warning(f"No Pete Alonso plays found for game {game_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Statcast data: {e}")
            return None
    
    def get_play_animation_url(self, game_id: int, play_id: int, statcast_data: Dict, mlb_play_data: Dict = None) -> Optional[str]:
        """Get the animation URL for a specific play from Baseball Savant"""
        try:
            # We need to get the play UUID from the Baseball Savant /gf endpoint
            logger.info(f"Getting play UUID for game {game_id}, play {play_id}")
            
            # Get game data from Baseball Savant /gf endpoint
            gf_url = f"{self.savant_base}/gf?game_pk={game_id}&at_bat_number=1"
            gf_response = requests.get(gf_url, timeout=15)
            
            if gf_response.status_code != 200:
                logger.warning(f"Failed to get game data from /gf endpoint: {gf_response.status_code}")
                return None
            
            gf_data = gf_response.json()
            
            # Look in both home and away team plays
            all_plays = []
            all_plays.extend(gf_data.get('team_home', []))
            all_plays.extend(gf_data.get('team_away', []))
            
            logger.info(f"Found {len(all_plays)} total plays in game data")
            
            # Find the matching Pete Alonso play
            target_play_uuid = None
            
            if mlb_play_data:
                target_event = mlb_play_data.get('result', {}).get('event', '').lower()
                target_inning = mlb_play_data.get('about', {}).get('inning')
                
                logger.info(f"Looking for Pete Alonso {target_event} in inning {target_inning}")
                
                # Try to find exact match - prioritize plays that have the actual event in their description
                best_matches = []
                for play in all_plays:
                    play_event = play.get('events', '').lower()
                    play_description = play.get('des', '').lower()
                    play_inning = play.get('inning')
                    play_batter = play.get('batter_name', '')
                    play_uuid = play.get('play_id')
                    
                    # Must match inning and have a play UUID
                    if str(play_inning) == str(target_inning) and play_uuid:
                        # Check if this is Pete Alonso
                        if 'alonso' in play_batter.lower():
                            # Score this match based on how well it matches the event
                            score = 0
                            
                            # HIGHEST PRIORITY: This is the actual contact pitch (not just a pitch in the at-bat)
                            pitch_call = play.get('pitch_call', '')
                            call = play.get('call', '')
                            if pitch_call == 'hit_into_play' or call == 'X':
                                score += 1000  # Heavily prioritize the contact pitch
                            
                            # High priority: event description contains the target event
                            if target_event in play_description or target_event.replace(' ', '') in play_description.replace(' ', ''):
                                score += 100
                            
                            # Medium priority: events field matches
                            if target_event in play_event or play_event in target_event:
                                score += 50
                            
                            # Add Alonso-specific bonus
                            if 'alonso' in play_batter.lower():
                                score += 25
                            
                            best_matches.append((score, play_uuid, play))
                            logger.debug(f"Match score {score}: {play_batter} - {play_description} ({pitch_call})")
                
                # Sort by score and take the best match
                if best_matches:
                    best_matches.sort(key=lambda x: x[0], reverse=True)
                    target_play_uuid = best_matches[0][1]
                    best_play = best_matches[0][2]
                    logger.info(f"Selected best match (score {best_matches[0][0]}): {best_play.get('batter_name')} - {best_play.get('des')}")
            
            if not target_play_uuid:
                logger.warning(f"Could not find matching play UUID for Pete Alonso in game {game_id}")
                return None
            
            # Try to get the video URL using the play UUID
            video_url = f"{self.savant_base}/sporty-videos/webm/{target_play_uuid}.webm"
            
            # Test if the URL exists
            test_response = requests.head(video_url, timeout=10)
            if test_response.status_code == 200:
                logger.info(f"Found video URL: {video_url}")
                return video_url
            else:
                logger.warning(f"Video URL not accessible: {video_url} (status: {test_response.status_code})")
                return None
                
        except Exception as e:
            logger.error(f"Error getting play animation URL: {e}")
            return None
    
    def download_and_convert_to_gif(self, video_url: str, output_path: str, max_duration: int = 10) -> bool:
        """Download video and convert to GIF using ffmpeg"""
        try:
            # Download the video
            temp_video = self.temp_dir / f"temp_video_{int(time.time())}.webm"
            
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(temp_video, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Convert to GIF using ffmpeg
            # Optimize for Twitter: max 15MB, good quality, reasonable frame rate
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(temp_video),
                '-t', str(max_duration),  # Limit duration
                '-vf', 'fps=15,scale=480:-1:flags=lanczos,palettegen=stats_mode=diff',
                '-y',
                str(self.temp_dir / 'palette.png')
            ]
            
            # Generate palette
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            
            # Create GIF with palette
            gif_cmd = [
                'ffmpeg',
                '-i', str(temp_video),
                '-i', str(self.temp_dir / 'palette.png'),
                '-t', str(max_duration),
                '-lavfi', 'fps=15,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5',
                '-y',
                output_path
            ]
            
            subprocess.run(gif_cmd, check=True, capture_output=True)
            
            # Clean up
            temp_video.unlink()
            (self.temp_dir / 'palette.png').unlink(missing_ok=True)
            
            # Check file size (Twitter limit is ~15MB for GIFs)
            if Path(output_path).stat().st_size > 15 * 1024 * 1024:
                logger.warning(f"GIF too large: {Path(output_path).stat().st_size / 1024 / 1024:.1f}MB")
                return False
            
            logger.info(f"Successfully created GIF: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error creating GIF: {e}")
            return False
    
    def get_gif_for_play(self, game_id: int, play_id: int, game_date: str, mlb_play_data: Dict = None) -> Optional[str]:
        """Create a GIF for a specific Pete Alonso play and return the file path"""
        try:
            logger.info(f"Creating GIF for Pete Alonso play - game {game_id}, play {play_id}")
            
            # Step 1: Get Statcast data for the play
            statcast_data = self.get_statcast_data_for_play(game_id, play_id, game_date, mlb_play_data)
            if not statcast_data:
                logger.warning(f"No Statcast data found for Pete Alonso play {play_id}")
                return None
            
            # Step 2: Get the animation URL
            animation_url = self.get_play_animation_url(game_id, play_id, statcast_data, mlb_play_data)
            if not animation_url:
                logger.warning(f"No animation URL found for Pete Alonso play {play_id}")
                return None
                
            # Step 3: Create the GIF
            event_type = mlb_play_data.get('result', {}).get('event', 'play').lower().replace(' ', '_')
            gif_filename = f"alonso_{event_type}_{game_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gif"
            gif_path = self.temp_dir / gif_filename
            
            success = self.download_and_convert_to_gif(animation_url, str(gif_path))
            
            if success and gif_path.exists():
                logger.info(f"Successfully created Pete Alonso GIF: {gif_path}")
                return str(gif_path)
            else:
                logger.error(f"Failed to create GIF for Pete Alonso play {play_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating GIF for Pete Alonso play {play_id}: {e}")
            return None

if __name__ == "__main__":
    # Test the integration
    gif_integration = BaseballSavantGIFIntegration()
    print("Pete Alonso Baseball Savant GIF integration module loaded successfully!") 