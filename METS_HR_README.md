# 🏟️ New York Mets Home Run Tracker

A specialized MLB tracking system that monitors **every single New York Mets home run** in real-time, automatically generating GIFs and posting to Discord with detailed statistics.

## 🎯 Features

- **Real-time Monitoring**: Checks for Mets games every 2 minutes
- **All Home Runs**: Captures every Mets HR regardless of impact (no WPA filtering)
- **Automatic GIF Creation**: Generates highlight GIFs via Baseball Savant integration
- **Discord Integration**: Posts formatted messages with stats and GIFs
- **Keep-alive System**: Prevents deployment sleeping with continuous pings
- **Web Dashboard**: Beautiful Mets-themed interface for monitoring and control
- **Comprehensive Logging**: Detailed tracking of all system activities

## 🛠️ Setup Instructions

### 1. Environment Variables

Set these environment variables in your deployment platform (Render, Heroku, etc.):

```
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
```

To get a Discord webhook URL:
1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook or use an existing one
4. Copy the webhook URL and set it as the DISCORD_WEBHOOK_URL environment variable

**Note**: Never commit webhook URLs to your code repository for security reasons.

### 2. Local Development (Optional)

If running locally, create a `.env` file:
```bash
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
```

### 3. Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables
4. Run: `python mets_homerun_tracker.py`

## 🚀 Deployment on Render

1. **Connect Repository**: Link your GitHub repository to Render
2. **Set Environment Variables**: 
   - Go to your service settings
   - Add `DISCORD_WEBHOOK_URL` with your webhook URL
3. **Deploy**: The system will automatically start monitoring

### Render Configuration:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python mets_homerun_tracker.py`
- **Environment**: Python 3.9+

## 📊 Dashboard

Access the web dashboard at your deployment URL to:
- View real-time system status
- Monitor today's home run statistics
- Start/stop the tracking system
- View recent activity logs

## 🎮 Discord Integration

When a Mets player hits a home run, the bot posts a message in this format:
```
[Player Name] goes yard! [Description] [Exit Velocity/Launch Angle stats] #LGM
```

Example:
```
Pete Alonso goes yard! 441-foot blast to center field! 108.2 mph exit velocity, 28° launch angle #LGM
```

## 🏗️ System Architecture

### Core Components:

1. **mets_homerun_tracker.py**: Main tracking system
   - Monitors Mets games (Team ID: 121)
   - Detects home runs from game feeds
   - Manages GIF generation queue
   - Handles Discord posting

2. **baseball_savant_gif_integration.py**: GIF creation
   - Interfaces with Baseball Savant
   - Downloads and processes highlight videos
   - Converts to GIF format

3. **discord_integration.py**: Discord posting
   - Formats messages with player stats
   - Uploads GIFs to Discord
   - Handles API rate limiting

4. **mets_dashboard.py**: Web interface
   - Real-time system monitoring
   - Mets-themed UI (orange/blue)
   - Control panel for system management

## 📈 Monitoring

The system provides comprehensive logging:
- System uptime and health
- Home runs detected and posted
- API call statistics
- Error tracking and recovery
- Queue management status

## 🔧 Key Features

### Real-time Detection
- Monitors all Mets games simultaneously
- 2-minute check intervals for optimal performance
- Immediate detection when games go live

### Smart Processing
- Duplicate detection prevents repeat posts
- Queue management for reliable GIF creation
- Retry logic for failed operations
- Automatic cleanup of old data

### Robust Architecture
- Keep-alive pings prevent deployment sleeping
- Error handling and recovery
- Rate limiting compliance
- Memory efficient processing

## 🎯 Mets-Specific Filtering

Unlike general MLB trackers, this system:
- Only monitors New York Mets games (Team ID: 121)
- Captures ALL Mets home runs (no impact filtering)
- Uses Mets branding and colors
- Includes #LGM hashtag for team pride

## 📱 Usage

Once deployed, the system runs automatically:

1. **Automatic Start**: Begins monitoring when deployed
2. **Game Detection**: Finds scheduled/live Mets games
3. **HR Monitoring**: Checks for new home runs every 2 minutes
4. **GIF Creation**: Generates highlights for each home run
5. **Discord Posting**: Shares formatted messages with stats
6. **Keep-alive**: Maintains continuous operation

## 🐛 Troubleshooting

### Common Issues:

1. **No Discord Posts**: Check DISCORD_WEBHOOK_URL environment variable
2. **System Sleeping**: Ensure keep-alive pings are working
3. **Missing GIFs**: Baseball Savant may have delays
4. **API Errors**: Check logs for rate limiting or connectivity issues

### Log Messages:
- `🔄 Starting monitoring cycle`: Normal operation
- `🎯 Found X Mets game(s)`: Games detected
- `⚾ NEW HOME RUN DETECTED`: Success!
- `💓 Keep-alive ping`: System health check

## 📄 License

This project is for educational and personal use. MLB data is property of Major League Baseball.

---

**Let's Go Mets! 🧡💙 #LGM** 