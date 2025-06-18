#!/usr/bin/env python3
"""
Standalone test for graphic generation only
This avoids importing tweepy and tests just the PIL graphic functionality
"""

import os
import logging
from datetime import datetime, timedelta
from io import BytesIO
import pytz
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Eastern timezone
eastern_tz = pytz.timezone('US/Eastern')

def get_font(size, bold=False):
    """Get font with fallback options"""
    try:
        if bold:
            return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
        else:
            return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except:
        try:
            # Windows fallback
            if bold:
                return ImageFont.truetype("arial.ttf", size)
            else:
                return ImageFont.truetype("arial.ttf", size)
        except:
            # Ultimate fallback
            return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def get_yesterday_date():
    """Get yesterday's date in MM/DD/YYYY format"""
    yesterday = datetime.now(eastern_tz) - timedelta(days=1)
    return yesterday.strftime("%m/%d/%Y")

def create_impact_plays_graphic(plays):
    """Create a single graphic with all 3 top impact plays using PIL"""
    try:
        # Image dimensions optimized for Twitter
        width, height = 1200, 1600
        
        # Create image with dark background
        img = Image.new('RGB', (width, height), color='#1a1a1a')
        draw = ImageDraw.Draw(img)
        
        # Colors
        white = '#ffffff'
        orange = '#ff6b35'
        light_gray = '#cccccc'
        yellow = '#ffff99'
        dark_panel = '#2a2a2a'
        
        # Rank colors (gold, silver, bronze)
        rank_colors = ['#ffd700', '#c0c0c0', '#cd7f32']
        
        # Fonts
        title_font = get_font(48, bold=True)
        subtitle_font = get_font(24)
        header_font = get_font(28, bold=True)
        text_font = get_font(20)
        small_font = get_font(16)
        
        # Main title
        title = "🔥 TOP 3 HIGHEST IMPACT MLB PLAYS 🔥"
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = bbox[2] - bbox[0]
        draw.text(((width - title_width) // 2, 30), title, fill=white, font=title_font)
        
        # Subtitle
        subtitle = f"From Yesterday's Games • {get_yesterday_date()}"
        bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        subtitle_width = bbox[2] - bbox[0]
        draw.text(((width - subtitle_width) // 2, 90), subtitle, fill=light_gray, font=subtitle_font)
        
        # Draw each play
        y_start = 160
        panel_height = 420
        margin = 40
        
        for i, play in enumerate(plays):
            y_pos = y_start + (i * (panel_height + 20))
            
            # Draw background panel
            draw.rectangle([margin, y_pos, width - margin, y_pos + panel_height], 
                         fill=dark_panel, outline=rank_colors[i], width=4)
            
            # Rank circle
            circle_x = margin + 60
            circle_y = y_pos + 60
            circle_radius = 35
            
            # Draw rank circle
            draw.ellipse([circle_x - circle_radius, circle_y - circle_radius,
                         circle_x + circle_radius, circle_y + circle_radius],
                        fill=rank_colors[i], outline=white, width=3)
            
            # Rank number
            rank_text = str(i + 1)
            bbox = draw.textbbox((0, 0), rank_text, font=header_font)
            rank_width = bbox[2] - bbox[0]
            rank_height = bbox[3] - bbox[1]
            draw.text((circle_x - rank_width // 2, circle_y - rank_height // 2), 
                     rank_text, fill='black', font=header_font)
            
            # Impact percentage (large, prominent)
            impact_pct = f"{play['impact']:.1%}"
            impact_text = f"Impact: {impact_pct}"
            draw.text((margin + 130, y_pos + 30), impact_text, fill=orange, font=header_font)
            
            # Game info
            away_team = play['game_info']['away_team']
            home_team = play['game_info']['home_team']
            away_score = play['game_info']['away_score']
            home_score = play['game_info']['home_score']
            
            game_text = f"{away_team} {away_score} - {home_score} {home_team}"
            draw.text((margin + 130, y_pos + 70), game_text, fill=white, font=text_font)
            
            # Inning info
            inning_text = f"Inning {play['inning']} ({play['half_inning']})"
            draw.text((margin + 130, y_pos + 105), inning_text, fill=light_gray, font=text_font)
            
            # Player matchup
            player_text = f"{play['batter']} vs {play['pitcher']}"
            # Truncate if too long
            if len(player_text) > 45:
                player_text = player_text[:42] + "..."
            draw.text((margin + 20, y_pos + 150), player_text, fill=white, font=text_font)
            
            # Play description (wrapped)
            description = play['description']
            if len(description) > 100:
                description = description[:97] + "..."
            
            # Wrap description text
            max_desc_width = width - (margin * 2) - 40
            desc_lines = wrap_text(description, text_font, max_desc_width, draw)
            
            # Draw description lines
            line_height = 25
            for j, line in enumerate(desc_lines[:4]):  # Max 4 lines
                draw.text((margin + 20, y_pos + 190 + (j * line_height)), 
                         line, fill=yellow, font=text_font)
            
            # Event type (prominent)
            event_text = f"• {play['event'].upper()}"
            draw.text((margin + 20, y_pos + 320), event_text, fill=rank_colors[i], font=text_font)
            
            # Impact bar visualization
            bar_x = margin + 20
            bar_y = y_pos + 360
            bar_max_width = width - (margin * 2) - 40
            bar_width = int(play['impact'] * bar_max_width / 0.5)  # Scale to max 50% impact
            bar_height = 20
            
            # Draw impact bar background
            draw.rectangle([bar_x, bar_y, bar_x + bar_max_width, bar_y + bar_height], 
                         fill='#444444', outline=light_gray, width=1)
            
            # Draw impact bar fill
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], 
                         fill=orange)
            
            # Impact percentage on bar
            bar_text = f"{impact_pct} WP Impact"
            bbox = draw.textbbox((0, 0), bar_text, font=small_font)
            text_width = bbox[2] - bbox[0]
            draw.text((bar_x + bar_max_width - text_width, bar_y + 25), 
                     bar_text, fill=orange, font=small_font)
        
        # Footer
        footer_text = "Generated by MLB Impact Tracker • Follow for daily updates"
        bbox = draw.textbbox((0, 0), footer_text, font=small_font)
        footer_width = bbox[2] - bbox[0]
        draw.text(((width - footer_width) // 2, height - 50), 
                 footer_text, fill='#888888', font=small_font)
        
        # Convert to BytesIO
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG', quality=95, optimize=True)
        img_buffer.seek(0)
        
        return img_buffer
        
    except Exception as e:
        logger.error(f"Error creating impact plays graphic: {str(e)}")
        return None

def create_test_plays():
    """Create test impact plays data"""
    test_plays = [
        {
            'impact': 0.287,  # 28.7% impact
            'game_info': {
                'away_team': 'New York Yankees',
                'home_team': 'Boston Red Sox', 
                'away_score': 6,
                'home_score': 5
            },
            'inning': 9,
            'half_inning': 'bottom',
            'batter': 'Rafael Devers',
            'pitcher': 'Clay Holmes',
            'description': 'Rafael Devers hits a walk-off home run to right field. The ball traveled 412 feet.',
            'event': 'Home Run'
        },
        {
            'impact': 0.234,  # 23.4% impact  
            'game_info': {
                'away_team': 'Los Angeles Dodgers',
                'home_team': 'San Francisco Giants',
                'away_score': 3,
                'home_score': 4
            },
            'inning': 8,
            'half_inning': 'top',
            'batter': 'Mookie Betts',
            'pitcher': 'Camilo Doval',
            'description': 'Mookie Betts doubles to deep center field. Freddie Freeman scores. Will Smith scores.',
            'event': 'Double'
        },
        {
            'impact': 0.156,  # 15.6% impact
            'game_info': {
                'away_team': 'Atlanta Braves', 
                'home_team': 'Philadelphia Phillies',
                'away_score': 2,
                'home_score': 3
            },
            'inning': 7,
            'half_inning': 'bottom',
            'batter': 'Bryce Harper',
            'pitcher': 'A.J. Minter',
            'description': 'Bryce Harper grounds into a double play. Nick Castellanos out at second. Trea Turner out at first.',
            'event': 'Grounded Into DP'
        }
    ]
    
    return test_plays

def main():
    """Main test function"""
    print("=" * 70)
    print("🚨 MLB IMPACT PLAYS GRAPHIC GENERATOR - TEST 🚨")
    print("=" * 70)
    
    logger.info("🎨 Testing PIL-based graphic generation...")
    
    # Create test data
    test_plays = create_test_plays()
    
    logger.info(f"📋 Created {len(test_plays)} test plays:")
    for i, play in enumerate(test_plays):
        logger.info(f"  {i+1}. {play['event']} - {play['impact']:.1%} impact ({play['game_info']['away_team']} vs {play['game_info']['home_team']})")
    
    # Test date function
    yesterday = get_yesterday_date()
    logger.info(f"📅 Yesterday's date: {yesterday}")
    
    # Generate the graphic
    logger.info("\n🎨 Generating graphic...")
    try:
        graphic_buffer = create_impact_plays_graphic(test_plays)
        
        if graphic_buffer:
            # Save the graphic to a file so we can see it
            filename = 'test_impact_plays.png'
            with open(filename, 'wb') as f:
                graphic_buffer.seek(0)
                f.write(graphic_buffer.read())
            
            logger.info("✅ SUCCESS: Graphic generated successfully!")
            logger.info(f"📁 Saved as: {filename}")
            logger.info("🖼️  Open the file to see the graphic")
            
            # Get file size
            file_size = os.path.getsize(filename)
            logger.info(f"📊 File size: {file_size:,} bytes")
            
            print("\n" + "=" * 70)
            print("✅ GRAPHIC GENERATION TEST PASSED!")
            print(f"🎨 Check out '{filename}' to see the generated graphic")
            print("🚀 The PIL-based graphic system is working perfectly!")
            print("📱 This graphic is optimized for Twitter posting")
            print("=" * 70)
            
        else:
            logger.error("❌ FAILED: Graphic generation returned None")
            print("\n" + "=" * 70)
            print("❌ GRAPHIC GENERATION TEST FAILED!")
            print("🔧 Check the error messages above")
            print("=" * 70)
            
    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        print("\n" + "=" * 70)
        print("❌ GRAPHIC GENERATION TEST FAILED!")
        print(f"🔧 Error: {str(e)}")
        print("=" * 70)

if __name__ == "__main__":
    main() 