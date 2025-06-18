#!/usr/bin/env python3
"""
Discord Integration for Mets Home Run Tracker
Handles posting to Discord webhook with GIF attachments
"""

import requests
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DiscordPoster:
    """Handles Discord webhook posting for Mets home runs"""
    
    def __init__(self, webhook_url=None):
        """Initialize Discord integration with webhook URL."""
        self.webhook_url = webhook_url
        if not self.webhook_url:
            raise ValueError("Discord webhook URL is required")
        
    def post_message(self, content: str, embeds: Optional[list] = None) -> bool:
        """Post a message to Discord"""
        try:
            payload = {"content": content}
            
            if embeds:
                payload["embeds"] = embeds
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Successfully posted to Discord")
            return True
            
        except Exception as e:
            logger.error(f"Error posting to Discord: {e}")
            return False
    
    def post_message_with_gif(self, message: str, gif_path: Optional[str] = None, title: Optional[str] = None) -> bool:
        """Post a message with optional GIF attachment"""
        try:
            if gif_path and os.path.exists(gif_path):
                # Upload GIF as file attachment
                with open(gif_path, 'rb') as gif_file:
                    files = {
                        'file': (os.path.basename(gif_path), gif_file, 'image/gif')
                    }
                    
                    data = {
                        'content': message
                    }
                    
                    response = requests.post(self.webhook_url, data=data, files=files, timeout=30)
                    response.raise_for_status()
                    
                    logger.info(f"Successfully posted message with GIF: {gif_path}")
                    return True
            else:
                # Just post the text message
                return self.post_message(message)
                
        except Exception as e:
            logger.error(f"Error posting message with GIF: {e}")
            return False

def get_discord_poster() -> Optional[DiscordPoster]:
    """Get a Discord poster instance with webhook URL from environment"""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URL environment variable not set")
        return None
    
    return DiscordPoster(webhook_url)

def post_home_run(player_name: str, description: str, stats: Dict[str, Any], gif_path: Optional[str] = None) -> bool:
    """
    Post a Mets home run to Discord with proper formatting
    
    Args:
        player_name: Name of the player who hit the home run
        description: Play description
        stats: Dictionary containing exit_velocity, launch_angle, distance
        gif_path: Optional path to GIF file
    
    Returns:
        bool: True if posted successfully
    """
    try:
        # Get Discord poster instance
        discord_poster = get_discord_poster()
        if not discord_poster:
            logger.error("Cannot post to Discord: webhook URL not configured")
            return False
        
        # Create message content
        message_content = f"🏠⚾ **{player_name}** goes yard! ⚾🏠\n\n"
        message_content += f"{description}\n"
        
        # Add Statcast data if available
        stats_line = []
        if stats.get('exit_velocity'):
            stats_line.append(f"Exit Velocity: {stats['exit_velocity']:.1f} mph")
        if stats.get('launch_angle'):
            stats_line.append(f"Launch Angle: {stats['launch_angle']:.0f}°")
        if stats.get('distance'):
            stats_line.append(f"Distance: {stats['distance']:.0f} ft")
        
        if stats_line:
            message_content += " | ".join(stats_line) + "\n"
        
        message_content += "\n#LGM"
        
        # Post to Discord
        return discord_poster.post_message_with_gif(
            message=message_content,
            gif_path=gif_path,
            title=f"Mets HR: {player_name}"
        )
        
    except Exception as e:
        logger.error(f"Error posting home run to Discord: {e}")
        return False

def test_webhook() -> bool:
    """Test the Discord webhook connection"""
    try:
        discord_poster = get_discord_poster()
        if not discord_poster:
            logger.error("Cannot test webhook: URL not configured")
            return False
            
        test_message = "🧪 Mets Home Run Tracker test message #LGM"
        return discord_poster.post_message(test_message)
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return False

if __name__ == "__main__":
    # Test the webhook
    print("Testing Discord webhook...")
    if test_webhook():
        print("✅ Discord webhook test successful!")
    else:
        print("❌ Discord webhook test failed!") 