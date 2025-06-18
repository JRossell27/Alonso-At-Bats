# 🏠⚾ Mets Home Run Tracker

**Real-time monitoring and Discord posting of every New York Mets home run with GIF generation**

## Overview

The Mets Home Run Tracker is a comprehensive system that monitors live MLB games in real-time to detect every New York Mets home run, creates GIFs of the plays using Baseball Savant integration, and posts them to Discord with enhanced Statcast data.

### Key Features

- 🎯 **Comprehensive Coverage**: Tracks ALL Mets home runs (no WPA filtering)
- 🎬 **Automatic GIF Creation**: Generates GIFs using Baseball Savant integration
- 📱 **Discord Integration**: Posts to Discord with formatted messages
- 📊 **Enhanced Stats**: Includes exit velocity, launch angle, and distance
- 🖥️ **Web Dashboard**: Beautiful Mets-themed monitoring interface
- ☁️ **Cloud Ready**: Optimized for Render.com deployment

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MLB API       │    │   Baseball       │    │   Discord       │
│   Live Games    │────│   Savant GIFs    │────│   Webhook       │
│   & Play Data   │    │   & Statcast     │    │   Posting       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Mets Home Run Tracker                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Monitor   │  │ GIF Queue   │  │    Web Dashboard        │ │
│  │   Games     │──│ Processing  │──│    (Flask)              │ │
│  │   (2 min)   │  │ (5 min)     │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- Required packages (see `requirements.txt`)

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/JRossell27/Mets_HRs.git
   cd Mets_HRs
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the tracker**:
   ```bash
   python mets_homerun_tracker.py
   ```

4. **Run the dashboard** (optional, in separate terminal):
   ```bash
   python mets_dashboard.py
   ```

### Discord Webhook Configuration

The system is pre-configured with the Discord webhook:
```
https://discord.com/api/webhooks/1384903371198038167/wpSac_BDyX4fNTQq4d9fWV31QtZlmCKkzcMhVZpWJF9ZtJLJY4tMZ2L_x9Kn7McGOIKB
```

To change the webhook, edit the `discord_webhook` variable in `mets_homerun_tracker.py`.

## Usage

### Running the Tracker

The tracker operates in continuous monitoring mode:

```bash
python mets_homerun_tracker.py
```

**What it does:**
- Checks for live Mets games every 2 minutes
- Detects ALL Mets home runs (no impact filtering)
- Queues home runs for GIF processing
- Posts to Discord with enhanced stats

### Web Dashboard

Access the dashboard at `http://localhost:5000` when running locally.

**Dashboard Features:**
- Real-time system status
- Start/stop monitoring controls
- Home run statistics
- Mets orange/blue theming
- Auto-refresh every 30 seconds

### Testing

Run the comprehensive test suite:

```bash
# Unit tests
python test_mets_tracker.py

# System integration test
python test_mets_tracker.py --system-test
```

## Discord Message Format

The system posts home runs with this format:

```
🏠⚾ **Pete Alonso** goes yard! ⚾🏠

Pete Alonso homers (15) on a fly ball to left center field.
Exit Velocity: 108.2 mph | Launch Angle: 27° | Distance: 425 ft

#LGM
```

## Technical Details

### Core Components

#### 1. MetsHomeRunTracker (`mets_homerun_tracker.py`)
- **Purpose**: Main monitoring and coordination
- **Key Features**:
  - Mets team ID filtering (121)
  - 2-minute monitoring cycles
  - Queue management with rate limiting
  - Baseball Savant Statcast integration

#### 2. Discord Integration (`discord_integration.py`)
- **Purpose**: Discord webhook posting
- **Features**:
  - Message formatting with Statcast data
  - GIF attachment support
  - Error handling and retry logic

#### 3. Web Dashboard (`mets_dashboard.py`)
- **Purpose**: Web interface for monitoring
- **Features**:
  - Mets-themed UI (orange/blue)
  - Real-time status updates
  - Start/stop controls
  - Keep-alive system

#### 4. Baseball Savant Integration (`baseball_savant_gif_integration.py`)
- **Purpose**: GIF creation and Statcast data
- **Features**:
  - Play matching and GIF generation
  - Enhanced metrics extraction
  - Rate limiting and retry logic

### Data Flow

1. **Game Detection**: Monitor live Mets games via MLB API
2. **Play Analysis**: Check each play for Mets home runs
3. **Queue Management**: Add home runs to processing queue
4. **GIF Creation**: Generate GIFs using Baseball Savant
5. **Statcast Enhancement**: Extract exit velocity, launch angle, distance
6. **Discord Posting**: Post formatted message with GIF

### Monitoring Cycle

```
Every 2 minutes:
├── Get live Mets games
├── For each game:
│   ├── Get all plays
│   ├── Check for Mets home runs
│   └── Queue new home runs
├── Process GIF queue (with 5-minute rate limiting)
└── Keep-alive ping
```

### Memory Management

- **Queue Size**: Limited to 20 items
- **Processed Plays**: Limited to 200 items
- **GIF Cleanup**: Files deleted after posting
- **Log Rotation**: Automatic log management

## Deployment

### Render.com Deployment

The system is optimized for Render.com with:

- `render.yaml`: Service configuration
- `startup.sh`: Launch script
- `Dockerfile`: Container configuration
- `requirements.txt`: Python dependencies

**Environment Variables:**
- `PORT`: Set automatically by Render
- `KEEP_ALIVE_URL`: Auto-configured for dashboard

### Deployment Files

- **render.yaml**: Render service configuration
- **startup.sh**: Startup script for deployment
- **Dockerfile**: Container configuration
- **requirements.txt**: Python package dependencies

## Configuration

### Key Settings

```python
# Mets team ID (do not change)
mets_team_id = 121

# Monitoring interval (seconds)
monitoring_interval = 120  # 2 minutes

# GIF processing rate limit
gif_rate_limit = 300  # 5 minutes between attempts

# Queue management
max_queue_size = 20
max_attempts = 5
```

### Discord Webhook

To change the Discord webhook, update the URL in `discord_integration.py`:

```python
self.webhook_url = "your_new_webhook_url_here"
```

## Troubleshooting

### Common Issues

1. **No home runs detected**:
   - Verify Mets are playing (check MLB schedule)
   - Check team ID filtering (121 for Mets)

2. **GIF creation failing**:
   - Baseball Savant rate limiting
   - Play data matching issues
   - Network connectivity

3. **Discord posting errors**:
   - Invalid webhook URL
   - Message size limits
   - Network issues

### Logging

The system provides comprehensive logging:

```bash
tail -f mets_homerun_tracker.log
```

**Log Levels:**
- `INFO`: Normal operations
- `WARNING`: Minor issues
- `ERROR`: Serious problems

### Debug Mode

Enable verbose logging by setting log level to DEBUG:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Adding Features

1. **New Discord Format**: Modify `post_to_discord()` in `mets_homerun_tracker.py`
2. **Additional Stats**: Enhance `get_enhanced_statcast_data()`
3. **Dashboard Features**: Add endpoints to `mets_dashboard.py`

### Testing Changes

Always run tests before deploying:

```bash
python test_mets_tracker.py --system-test
```

### Code Structure

```
mets_homerun_tracker.py    # Main tracker logic
├── MetsHomeRun           # Data structure
├── MetsHomeRunTracker    # Main class
└── monitoring loop       # Continuous operation

discord_integration.py     # Discord posting
├── DiscordPoster         # Main class
└── post_home_run()       # Helper function

mets_dashboard.py          # Web interface
├── Flask routes          # API endpoints
└── HTML template         # Dashboard UI

baseball_savant_gif_integration.py  # GIF creation
└── BaseballSavantGifGenerator      # Main class
```

## License

This project is for personal use and educational purposes.

## Support

For issues or questions:
1. Check the logs for error messages
2. Run the system test: `python test_mets_tracker.py --system-test`
3. Verify Discord webhook connectivity
4. Check Render deployment logs

---

**Let's Go Mets! #LGM 🧡💙**

*Made with ❤️ for the best fans in baseball* 