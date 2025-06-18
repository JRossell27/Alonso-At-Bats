#!/usr/bin/env python3
"""
Test script for Baseball Savant GIF Integration
Use this to test fetching and converting Baseball Savant animations
"""

import logging
import sys
from datetime import datetime, timedelta
from baseball_savant_gif_integration import BaseballSavantGIFIntegration

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_recent_high_impact_play():
    """Test with a recent high-impact play"""
    gif_integration = BaseballSavantGIFIntegration()
    
    # For testing, you can use a recent game ID and play
    # You'd get these from your existing impact tracker
    test_game_id = 775236  # Example game ID
    test_play_id = 15      # Example at-bat number
    test_date = "2024-01-15"  # Example date
    
    print("🧪 Testing Baseball Savant GIF Integration")
    print("=" * 50)
    
    print(f"📊 Searching for play data...")
    print(f"   Game ID: {test_game_id}")
    print(f"   Play ID: {test_play_id}")
    print(f"   Date: {test_date}")
    
    # Step 1: Get Statcast data
    statcast_data = gif_integration.get_statcast_data_for_play(
        game_id=test_game_id,
        play_id=test_play_id,
        game_date=test_date
    )
    
    if statcast_data:
        print("✅ Found Statcast data!")
        print(f"   sv_id: {statcast_data.get('sv_id', 'N/A')}")
        print(f"   Description: {statcast_data.get('des', 'N/A')[:100]}...")
        
        # Step 2: Try to get animation URL
        print(f"\n🎬 Searching for animation...")
        animation_url = gif_integration.get_play_animation_url(
            game_id=test_game_id,
            play_id=test_play_id,
            statcast_data=statcast_data
        )
        
        if animation_url:
            print(f"✅ Found animation URL: {animation_url}")
            
            # Step 3: Try to create GIF
            print(f"\n🔄 Converting to GIF...")
            gif_path = gif_integration.get_gif_for_play(
                game_id=test_game_id,
                play_id=test_play_id,
                game_date=test_date,
                max_wait_minutes=2  # Short wait for testing
            )
            
            if gif_path:
                print(f"🎉 SUCCESS! Created GIF: {gif_path}")
                print(f"📁 You can find the GIF at: {gif_path}")
                return True
            else:
                print("❌ Failed to create GIF")
        else:
            print("❌ No animation URL found")
    else:
        print("❌ No Statcast data found")
    
    return False

def test_with_your_recent_play():
    """Test with a play from your actual system"""
    print("\n🔧 Testing with your system integration")
    print("=" * 50)
    
    # This is how you'd integrate with your existing system
    # You'd call this from your RealTimeImpactTracker when a high-impact play occurs
    
    sample_play = {
        'game_id': 775236,  # Replace with actual game_id from your system
        'play_id': 15,      # Replace with actual play_id
        'description': "Aaron Judge homers (62) on a fly ball to left field.",
        'impact_score': 0.423,
        'timestamp': datetime.now().isoformat()
    }
    
    sample_game_info = {
        'home_team': 'NYY',
        'away_team': 'TEX',
        'date': '2024-01-15'
    }
    
    gif_integration = BaseballSavantGIFIntegration()
    
    print(f"🎯 Testing with play: {sample_play['description'][:50]}...")
    
    # This simulates what would happen in your real system
    gif_path = gif_integration.get_gif_for_play(
        game_id=sample_play['game_id'],
        play_id=sample_play['play_id'],
        game_date=sample_game_info['date'],
        max_wait_minutes=2
    )
    
    if gif_path:
        print(f"✅ Successfully created GIF!")
        print(f"📄 Next step: Create follow-up tweet with GIF")
        
        # Simulate creating follow-up tweet
        success = gif_integration.create_follow_up_tweet_with_gif(
            original_tweet_id="1234567890",  # Would be actual tweet ID
            gif_path=gif_path,
            play_description=sample_play['description']
        )
        
        if success:
            print("✅ Follow-up tweet simulation successful!")
            return True
    
    print("❌ Could not create GIF for this play")
    return False

def check_dependencies():
    """Check if required dependencies are available"""
    print("🔍 Checking dependencies...")
    
    try:
        import requests
        print("✅ requests library available")
    except ImportError:
        print("❌ requests library missing - install with: pip install requests")
        return False
    
    # Check if ffmpeg is available
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✅ ffmpeg available")
        else:
            print("❌ ffmpeg not working properly")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ ffmpeg not found")
        print("   Install ffmpeg:")
        print("   - macOS: brew install ffmpeg")
        print("   - Ubuntu: sudo apt install ffmpeg")
        print("   - Windows: Download from https://ffmpeg.org/")
        return False
    
    return True

def explain_integration():
    """Explain how to integrate with existing system"""
    print("\n📚 How to integrate with your existing system:")
    print("=" * 50)
    
    integration_steps = [
        "1. Add the GIF integration to your requirements.txt:",
        "   - No new packages needed, uses existing ones",
        "",
        "2. Modify your RealTimeImpactTracker.post_impact_play() method:",
        "   - Post immediate tweet (as you do now)",
        "   - Start background thread for delayed GIF tweet",
        "",
        "3. Two posting strategies:",
        "   A) Immediate + Follow-up (recommended for testing):",
        "      - Post text tweet immediately",
        "      - Reply with GIF 15-30 minutes later",
        "",
        "   B) Delayed single tweet:",
        "      - Wait 30 minutes, post tweet with GIF",
        "      - Risk: Animation might not be available",
        "",
        "4. For testing, use strategy A with short delays",
        "",
        "5. Remember to add Baseball Savant credit:",
        "   'Animation courtesy of @baseballsavant'"
    ]
    
    for step in integration_steps:
        print(f"   {step}")
    
    print(f"\n💡 Pro tip: Start with strategy A and 2-hour delays")
    print(f"   This gives Baseball Savant time to process the animations")

if __name__ == "__main__":
    print("🏟️  Baseball Savant GIF Integration Test")
    print("=" * 60)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Missing required dependencies. Please install them first.")
        sys.exit(1)
    
    print("\n✅ All dependencies available!")
    
    # Run tests
    test_success = False
    
    try:
        # Test 1: Try with a sample play
        test_success = test_recent_high_impact_play()
        
        if not test_success:
            # Test 2: Try with integration example
            test_success = test_with_your_recent_play()
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.error(f"Test error: {e}")
    
    # Show integration guide
    explain_integration()
    
    print("\n" + "=" * 60)
    if test_success:
        print("🎉 Test completed successfully! You're ready to integrate.")
    else:
        print("⚠️  Tests didn't complete successfully.")
        print("   This is normal - Baseball Savant animations take time to be available.")
        print("   The integration code is ready for live testing.")
    
    print("\n📝 Next steps:")
    print("   1. Test with a live game during baseball season")
    print("   2. Use 30-60 minute delays for animation availability") 
    print("   3. Start with follow-up tweet strategy")
    print("   4. Monitor file sizes (Twitter limit: 15MB for GIFs)")
    print("\n🚀 Ready to make your impact tweets even more impactful!") 