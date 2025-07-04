#!/usr/bin/env python3
"""
Mets Home Run Tracker Dashboard
Flask web interface for monitoring and controlling the Mets HR system
"""

from flask import Flask, render_template_string, jsonify, request
import threading
import time
import os
import requests
from datetime import datetime
from mets_homerun_tracker import MetsHomeRunTracker
import logging

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mets_dashboard.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global tracker instance - auto-start on startup
tracker = None
tracker_thread = None
auto_started = False

# Dashboard HTML template with Mets colors
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mets Home Run Tracker Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #ff5910 0%, #002d72 100%);
            color: white;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.3);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #ff5910;
            padding-bottom: 20px;
        }
        
        .header h1 {
            color: #ff5910;
            font-size: 2.5em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        
        .header .subtitle {
            color: #ffffff;
            font-size: 1.2em;
            margin-top: 10px;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .status-card {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #ff5910;
            backdrop-filter: blur(5px);
        }
        
        .status-card h3 {
            color: #ff5910;
            margin-top: 0;
            font-size: 1.1em;
        }
        
        .status-value {
            font-size: 1.5em;
            font-weight: bold;
            color: white;
        }
        
        .controls {
            text-align: center;
            margin: 30px 0;
            display: none; /* Hide controls since it's auto-running */
        }
        
        .btn {
            background: #ff5910;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            margin: 0 10px;
            transition: all 0.3s ease;
            text-transform: uppercase;
            font-weight: bold;
            letter-spacing: 1px;
        }
        
        .btn:hover {
            background: #e04a0d;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 89, 16, 0.4);
        }
        
        .btn:disabled {
            background: #666;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .btn.stop {
            background: #002d72;
        }
        
        .btn.stop:hover {
            background: #001f4d;
        }
        
        .stats-section {
            margin-top: 30px;
        }
        
        .stats-section h2 {
            color: #ff5910;
            border-bottom: 2px solid #ff5910;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        
        .recent-hrs {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .hr-item {
            background: rgba(0, 45, 114, 0.3);
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #ff5910;
        }
        
        .hr-player {
            font-weight: bold;
            color: #ff5910;
            font-size: 1.1em;
        }
        
        .hr-description {
            color: #ffffff;
            margin: 5px 0;
        }
        
        .hr-time {
            color: #ccc;
            font-size: 0.9em;
        }
        
        .refresh-info {
            text-align: center;
            color: #ccc;
            margin-top: 20px;
            font-style: italic;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-active {
            background: #4CAF50;
            animation: pulse 2s infinite;
        }
        
        .status-inactive {
            background: #f44336;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            color: #ccc;
        }
        
        .auto-status {
            background: rgba(76, 175, 80, 0.2);
            border: 1px solid #4CAF50;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
        }
        
        .auto-status h3 {
            color: #4CAF50;
            margin: 0 0 10px 0;
        }
        
        .logs-section {
            margin-top: 30px;
        }
        
        .log-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            border-left: 3px solid #ff5910;
        }
    </style>
    <script>
        function refreshStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('monitoring-status').innerHTML = 
                        data.monitoring ? 
                        '<span class="status-indicator status-active"></span>Active & Auto-Running' : 
                        '<span class="status-indicator status-inactive"></span>Stopped';
                    
                    document.getElementById('uptime').textContent = data.uptime || 'Not started';
                    document.getElementById('last-check').textContent = data.last_check || 'Never';
                    document.getElementById('queue-size').textContent = data.queue_size || 0;
                    document.getElementById('hrs-posted').textContent = data.stats.homeruns_posted_today || 0;
                    document.getElementById('gifs-created').textContent = data.stats.gifs_created_today || 0;
                    document.getElementById('hrs-queued').textContent = data.stats.homeruns_queued_today || 0;
                    document.getElementById('processed-plays').textContent = data.processed_plays || 0;
                    
                    // Update button states (hidden anyway)
                    document.getElementById('start-btn').disabled = data.monitoring;
                    document.getElementById('stop-btn').disabled = !data.monitoring;
                })
                .catch(error => {
                    console.error('Error fetching status:', error);
                    document.getElementById('monitoring-status').innerHTML = 
                        '<span class="status-indicator status-inactive"></span>Error';
                });
        }
        
        function refreshLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    const logsContainer = document.getElementById('logs-container');
                    logsContainer.innerHTML = '';
                    
                    data.logs.forEach(log => {
                        const logDiv = document.createElement('div');
                        logDiv.className = 'log-item';
                        logDiv.textContent = log;
                        logsContainer.appendChild(logDiv);
                    });
                })
                .catch(error => {
                    console.error('Error fetching logs:', error);
                });
        }
        
        function startMonitoring() {
            fetch('/api/start', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        setTimeout(refreshStatus, 1000);
                    } else {
                        alert('Failed to start monitoring: ' + data.error);
                    }
                });
        }
        
        function stopMonitoring() {
            fetch('/api/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        setTimeout(refreshStatus, 1000);
                    } else {
                        alert('Failed to stop monitoring: ' + data.error);
                    }
                });
        }
        
        function keepAlive() {
            fetch('/api/ping')
                .then(response => response.json())
                .catch(error => console.error('Keep-alive error:', error));
        }
        
        function testDiscord() {
            const button = document.getElementById('test-discord-btn');
            const statusDiv = document.getElementById('discord-test-status');
            
            // Disable button and show loading
            button.disabled = true;
            button.textContent = 'Testing...';
            statusDiv.innerHTML = '🔄 Testing Discord webhook...';
            statusDiv.style.color = '#ff5910';
            
            fetch('/api/test-discord', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        statusDiv.innerHTML = '✅ ' + data.message;
                        statusDiv.style.color = '#4CAF50';
                    } else {
                        statusDiv.innerHTML = '❌ ' + data.error;
                        statusDiv.style.color = '#f44336';
                    }
                })
                .catch(error => {
                    statusDiv.innerHTML = '❌ Network error: ' + error.message;
                    statusDiv.style.color = '#f44336';
                })
                .finally(() => {
                    // Re-enable button
                    button.disabled = false;
                    button.textContent = 'Test Discord Webhook';
                    
                    // Clear status after 10 seconds
                    setTimeout(() => {
                        statusDiv.innerHTML = '';
                    }, 10000);
                });
        }
        
        // Auto-refresh every 30 seconds
        setInterval(refreshStatus, 30000);
        
        // Refresh logs every 60 seconds
        setInterval(refreshLogs, 60000);
        
        // Keep-alive ping every 5 minutes
        setInterval(keepAlive, 300000);
        
        // Initial load
        document.addEventListener('DOMContentLoaded', function() {
            refreshStatus();
            refreshLogs();
        });
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠⚾ Mets Home Run Tracker</h1>
            <div class="subtitle">Real-time monitoring of every Mets home run with GIF generation</div>
        </div>
        
        <div class="auto-status">
            <h3>🤖 Automatic Background Service</h3>
            <p>This tracker runs continuously in the background, monitoring every Mets game for home runs. No manual intervention required!</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>Monitoring Status</h3>
                <div class="status-value" id="monitoring-status">
                    <span class="status-indicator status-inactive"></span>Loading...
                </div>
            </div>
            
            <div class="status-card">
                <h3>System Uptime</h3>
                <div class="status-value" id="uptime">--</div>
            </div>
            
            <div class="status-card">
                <h3>Last Check</h3>
                <div class="status-value" id="last-check">--</div>
            </div>
            
            <div class="status-card">
                <h3>Queue Size</h3>
                <div class="status-value" id="queue-size">--</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn" id="start-btn" onclick="startMonitoring()">Start Monitoring</button>
            <button class="btn stop" id="stop-btn" onclick="stopMonitoring()">Stop Monitoring</button>
        </div>
        
        <div class="stats-section">
            <h2>📊 Today's Statistics</h2>
            <div class="status-grid">
                <div class="status-card">
                    <h3>Home Runs Posted</h3>
                    <div class="status-value" id="hrs-posted">--</div>
                </div>
                
                <div class="status-card">
                    <h3>GIFs Created</h3>
                    <div class="status-value" id="gifs-created">--</div>
                </div>
                
                <div class="status-card">
                    <h3>Home Runs Queued</h3>
                    <div class="status-value" id="hrs-queued">--</div>
                </div>
                
                <div class="status-card">
                    <h3>Processed Plays</h3>
                    <div class="status-value" id="processed-plays">--</div>
                </div>
            </div>
        </div>
        
        <div class="stats-section">
            <h2>🧪 Discord Integration Test</h2>
            <div class="status-card" style="text-align: center; max-width: 500px; margin: 0 auto;">
                <h3>Test Discord Webhook</h3>
                <p style="color: #ccc; margin: 10px 0;">Click below to send a test message to your Discord channel and verify the webhook is working correctly.</p>
                <button class="btn" id="test-discord-btn" onclick="testDiscord()">Test Discord Webhook</button>
                <div id="discord-test-status" style="margin-top: 15px; font-weight: bold;"></div>
            </div>
        </div>
        
        <div class="logs-section">
            <h2>📄 Recent Activity Logs</h2>
            <div id="logs-container">
                <div class="log-item">Loading recent logs...</div>
            </div>
        </div>
        
        <div class="refresh-info">
            🔄 Dashboard refreshes automatically every 30 seconds<br>
            📄 Logs refresh every 60 seconds<br>
            ❤️ Keep-alive ping sent every 5 minutes<br>
            🤖 Background service runs continuously
        </div>
        
        <div class="footer">
            <p>Let's Go Mets! #LGM 🧡💙</p>
            <p>Made with ❤️ for the best fans in baseball</p>
        </div>
    </div>
</body>
</html>
'''

def auto_start_tracker():
    """Automatically start the tracker when the dashboard starts"""
    global tracker, tracker_thread, auto_started
    
    if not auto_started:
        logger.info("🤖 Auto-starting Mets Home Run Tracker background service...")
        
        try:
            tracker = MetsHomeRunTracker()
            
            def run_tracker():
                try:
                    # Get keep-alive URL for this dashboard
                    base_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://mets-hrs.onrender.com')
                    keep_alive_url = f"{base_url}/api/ping"
                    logger.info(f"🔄 Keep-alive URL: {keep_alive_url}")
                    
                    tracker.monitor_mets_home_runs(keep_alive_url)
                except Exception as e:
                    logger.error(f"💥 Tracker error: {e}")
            
            tracker_thread = threading.Thread(target=run_tracker, daemon=True)
            tracker_thread.start()
            auto_started = True
            
            logger.info("✅ Mets Home Run Tracker auto-started successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to auto-start tracker: {e}")

@app.route('/')
def dashboard():
    """Main dashboard page"""
    # Auto-start tracker on first page load
    auto_start_tracker()
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def get_status():
    """Get current system status"""
    global tracker
    
    if tracker:
        status = tracker.get_status()
    else:
        status = {
            'monitoring': False,
            'processing_gifs': False,
            'uptime': None,
            'last_check': None,
            'queue_size': 0,
            'processed_plays': 0,
            'stats': {
                'homeruns_posted_today': 0,
                'gifs_created_today': 0,
                'homeruns_queued_today': 0
            }
        }
    
    return jsonify(status)

@app.route('/api/logs')
def get_logs():
    """Get recent log entries"""
    try:
        log_lines = []
        
        # Try to read from multiple log files
        log_files = ['mets_dashboard.log', 'mets_homerun_tracker.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        # Get last 10 lines from each file
                        recent_lines = lines[-10:] if len(lines) > 10 else lines
                        for line in recent_lines:
                            if line.strip():
                                log_lines.append(line.strip())
                except Exception as e:
                    logger.error(f"Error reading {log_file}: {e}")
        
        # Sort by timestamp and keep most recent 20
        log_lines = sorted(log_lines)[-20:]
        
        if not log_lines:
            log_lines = [f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - System started, waiting for activity..."]
        
        return jsonify({'logs': log_lines})
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({'logs': [f"Error retrieving logs: {e}"]})

@app.route('/api/start', methods=['POST'])
def start_monitoring():
    """Start the monitoring system"""
    global tracker, tracker_thread
    
    try:
        if tracker and tracker.monitoring_active:
            return jsonify({'success': False, 'error': 'Already monitoring'})
        
        # Create new tracker instance
        tracker = MetsHomeRunTracker()
        
        # Start monitoring in background thread
        def run_tracker():
            try:
                # Get keep-alive URL for this dashboard
                base_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://mets-hrs.onrender.com')
                keep_alive_url = f"{base_url}/api/ping"
                tracker.monitor_mets_home_runs(keep_alive_url)
            except Exception as e:
                logger.error(f"Tracker error: {e}")
        
        tracker_thread = threading.Thread(target=run_tracker, daemon=True)
        tracker_thread.start()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    """Stop the monitoring system"""
    global tracker, tracker_thread
    
    try:
        if tracker:
            tracker.stop_monitoring()
        
        # Reset global variables
        tracker = None
        tracker_thread = None
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ping')
def ping():
    """Keep-alive endpoint"""
    logger.info("💓 Keep-alive ping received")
    return jsonify({
        'status': 'alive', 
        'timestamp': datetime.now().isoformat(),
        'service': 'mets-homerun-tracker'
    })

@app.route('/api/test-discord', methods=['POST'])
def test_discord():
    """Test Discord webhook connection"""
    try:
        from discord_integration import test_webhook
        
        logger.info("🧪 Testing Discord webhook...")
        success = test_webhook()
        
        if success:
            logger.info("✅ Discord webhook test successful!")
            return jsonify({
                'success': True, 
                'message': 'Discord webhook test successful! Check your Discord channel.'
            })
        else:
            logger.error("❌ Discord webhook test failed!")
            return jsonify({
                'success': False, 
                'error': 'Discord webhook test failed. Check your webhook URL and server permissions.'
            })
            
    except Exception as e:
        logger.error(f"❌ Discord test error: {e}")
        return jsonify({
            'success': False, 
            'error': f'Discord test error: {str(e)}'
        })

@app.route('/health')
def health_check():
    """Health check endpoint for deployment platforms"""
    return jsonify({
        'status': 'healthy',
        'service': 'mets-homerun-tracker',
        'timestamp': datetime.now().isoformat(),
        'auto_started': auto_started,
        'monitoring_active': tracker.monitoring_active if tracker else False
    })

def run_dashboard(host='0.0.0.0', port=None, debug=False):
    """Run the dashboard with proper configuration"""
    # Get port from environment or use default
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    
    # Configure logging
    if not debug:
        import logging
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    logger.info(f"🚀 Starting Mets Home Run Tracker Dashboard on {host}:{port}")
    logger.info(f"🔗 Dashboard will be available at: https://mets-hrs.onrender.com")
    logger.info(f"🤖 Background tracker will auto-start on first page load")
    
    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    except Exception as e:
        logger.error(f"❌ Failed to start dashboard: {e}")
        raise

if __name__ == '__main__':
    # Run dashboard
    run_dashboard(debug=False) 