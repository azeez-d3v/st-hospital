import sys
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import asyncio
import logging
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import HEADERS, DATA_PROVIDER_URLS, EMAIL_CONFIG
from utils.fetcher import LinkFetcher
from streamlit_autorefresh import st_autorefresh

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('src', 'scheduler.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('hospital_fetcher')

# Set page config
st.set_page_config(
    page_title="Hospital Data Fetcher",
    page_icon="🏥",
    layout="wide"
)

# Helper function to get source key - defining this early before it's used
def get_source_key(country, url):
    """Generate a unique key for each data source"""
    if "public-hospitals" in url:
        return f"{country}_public"
    elif "private-hospitals" in url:
        return f"{country}_private"
    elif "declared-hospitals" in url:
        return f"{country}_declared"
    else:
        return f"{country}_{url.split('/')[-1]}"

# Initialize session state for data sources
if 'active_sources' not in st.session_state:
    # Initialize with all sources enabled by default
    st.session_state.active_sources = {}
    for country, urls in DATA_PROVIDER_URLS.items():
        for url in urls:
            source_key = get_source_key(country, url)
            st.session_state.active_sources[source_key] = True

# Initialize session state
if 'fetcher' not in st.session_state:
    st.session_state.fetcher = LinkFetcher(
        headers=HEADERS,
        urls=DATA_PROVIDER_URLS,
        download_dir=os.path.join('src', 'data', 'downloads')
    )

if 'last_run_time' not in st.session_state:
    st.session_state.last_run_time = None

# Initialize scheduling session state
if 'schedule_enabled' not in st.session_state:
    st.session_state.schedule_enabled = False
if 'schedule_type' not in st.session_state:
    st.session_state.schedule_type = "hourly"
if 'schedule_hour' not in st.session_state:
    st.session_state.schedule_hour = 0
if 'schedule_minute' not in st.session_state:
    st.session_state.schedule_minute = 0
if 'schedule_day' not in st.session_state:
    st.session_state.schedule_day = 1
if 'schedule_weekday' not in st.session_state:
    st.session_state.schedule_weekday = 0
if 'custom_minutes' not in st.session_state:
    st.session_state.custom_minutes = 60  # Default to 60 minutes
if 'schedule_interval_ms' not in st.session_state:
    st.session_state.schedule_interval_ms = 3600000  # Default 1 hour in ms
if 'next_run_time' not in st.session_state:
    st.session_state.next_run_time = None
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'run_fetch_on_next_rerun' not in st.session_state:
    st.session_state.run_fetch_on_next_rerun = False

# Load schedule settings from JSON if available
schedule_config_file = os.path.join('src', 'data', 'config', 'schedule_config.json')
if os.path.exists(schedule_config_file):
    try:
        with open(schedule_config_file, 'r') as f:
            schedule_config = json.load(f)
            st.session_state.schedule_enabled = schedule_config.get('schedule_enabled', False)
            st.session_state.schedule_type = schedule_config.get('schedule_type', 'hourly')
            st.session_state.schedule_hour = schedule_config.get('schedule_hour', 0)
            st.session_state.schedule_minute = schedule_config.get('schedule_minute', 0)
            st.session_state.schedule_day = schedule_config.get('schedule_day', 1)
            st.session_state.schedule_weekday = schedule_config.get('schedule_weekday', 0)
            st.session_state.custom_minutes = schedule_config.get('custom_minutes', 60)
            # Don't load dynamic values like next_run_time and interval_ms
            logger.info("Loaded schedule configuration from file")
    except Exception as e:
        logger.error(f"Failed to load schedule configuration: {str(e)}")

# Initialize the input widget state values
if 'schedule_minute_hourly' not in st.session_state:
    st.session_state.schedule_minute_hourly = st.session_state.schedule_minute
if 'schedule_hour_daily' not in st.session_state:
    st.session_state.schedule_hour_daily = st.session_state.schedule_hour
if 'schedule_minute_daily' not in st.session_state:
    st.session_state.schedule_minute_daily = st.session_state.schedule_minute
if 'schedule_hour_weekly' not in st.session_state:
    st.session_state.schedule_hour_weekly = st.session_state.schedule_hour
if 'schedule_minute_weekly' not in st.session_state:
    st.session_state.schedule_minute_weekly = st.session_state.schedule_minute
if 'schedule_day_monthly' not in st.session_state:
    st.session_state.schedule_day_monthly = st.session_state.schedule_day
if 'schedule_hour_monthly' not in st.session_state:
    st.session_state.schedule_hour_monthly = st.session_state.schedule_hour
if 'schedule_minute_monthly' not in st.session_state:
    st.session_state.schedule_minute_monthly = st.session_state.schedule_minute
if 'custom_minutes_input' not in st.session_state:
    st.session_state.custom_minutes_input = st.session_state.custom_minutes

# Initialize email notification settings
if 'email_recipients' not in st.session_state:
    # Check if there's a saved email list
    email_file = os.path.join('src', 'data', 'config', 'email_recipients.json')
    if os.path.exists(email_file):
        try:
            with open(email_file, 'r') as f:
                st.session_state.email_recipients = json.load(f)
        except:
            st.session_state.email_recipients = []
    else:
        st.session_state.email_recipients = []

if 'smtp_server' not in st.session_state:
    st.session_state.smtp_server = EMAIL_CONFIG["SMTP_SERVER"]
if 'smtp_port' not in st.session_state:
    st.session_state.smtp_port = EMAIL_CONFIG["SMTP_PORT"]
if 'smtp_use_tls' not in st.session_state:
    st.session_state.smtp_use_tls = EMAIL_CONFIG["USE_TLS"]
if 'sender_email' not in st.session_state:
    st.session_state.sender_email = ""
if 'sender_password' not in st.session_state:
    st.session_state.sender_password = ""
if 'email_notifications_enabled' not in st.session_state:
    st.session_state.email_notifications_enabled = False

# Load email settings from JSON if available
email_config_file = os.path.join('src', 'data', 'config', 'email_config.json')
if os.path.exists(email_config_file):
    try:
        with open(email_config_file, 'r') as f:
            email_config = json.load(f)
            st.session_state.email_notifications_enabled = email_config.get('email_notifications_enabled', False)
            st.session_state.smtp_server = email_config.get('smtp_server', EMAIL_CONFIG["SMTP_SERVER"])
            st.session_state.smtp_port = email_config.get('smtp_port', EMAIL_CONFIG["SMTP_PORT"])
            st.session_state.smtp_use_tls = email_config.get('smtp_use_tls', EMAIL_CONFIG["USE_TLS"])
            st.session_state.sender_email = email_config.get('sender_email', "")
            st.session_state.sender_password = email_config.get('sender_password', "")
            logger.info("Loaded email configuration from file")
    except Exception as e:
        logger.error(f"Failed to load email configuration: {str(e)}")

def run_async(coroutine):
    """Helper function to run async code in a synchronous context"""
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(coroutine)
    loop.close()
    return result

def calculate_next_run_time():
    """Calculate the next run time based on the schedule settings"""
    now = datetime.now()
    
    if st.session_state.schedule_type == "hourly":
        # Run at the specified minute of each hour
        if now.minute >= st.session_state.schedule_minute:
            next_run = now.replace(minute=st.session_state.schedule_minute, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_run = now.replace(minute=st.session_state.schedule_minute, second=0, microsecond=0)
    
    elif st.session_state.schedule_type == "daily":
        # Run at the specified hour and minute each day
        target_time = now.replace(hour=st.session_state.schedule_hour, 
                                minute=st.session_state.schedule_minute, 
                                second=0, microsecond=0)
        if now >= target_time:
            next_run = target_time + timedelta(days=1)
        else:
            next_run = target_time
    
    elif st.session_state.schedule_type == "weekly":
        # Run on specified weekday (0=Monday, 6=Sunday) at specified time
        days_ahead = st.session_state.schedule_weekday - now.weekday()
        
        # Create target time for comparison
        target_time = now.replace(hour=st.session_state.schedule_hour,
                                 minute=st.session_state.schedule_minute,
                                 second=0, microsecond=0)
        
        # If it's the same day but time has passed, schedule for next week
        if days_ahead == 0 and now >= target_time:
            days_ahead = 7
        # If it's a day in the past this week, schedule for next week
        elif days_ahead < 0:
            days_ahead += 7
            
        # Calculate the next run time
        next_run = (now.replace(hour=st.session_state.schedule_hour,
                              minute=st.session_state.schedule_minute,
                              second=0, microsecond=0) + 
                   timedelta(days=days_ahead))
    
    elif st.session_state.schedule_type == "monthly":
        # Run on specified day of month at specified time
        target_day = min(st.session_state.schedule_day, 28)  # To avoid month boundary issues
        
        if now.day > target_day or (now.day == target_day and 
                                   (now.hour > st.session_state.schedule_hour or 
                                    (now.hour == st.session_state.schedule_hour and 
                                     now.minute >= st.session_state.schedule_minute))):
            # Go to next month
            if now.month == 12:
                next_run = datetime(now.year + 1, 1, target_day, 
                                   st.session_state.schedule_hour, 
                                   st.session_state.schedule_minute)
            else:
                next_run = datetime(now.year, now.month + 1, target_day,
                                   st.session_state.schedule_hour,
                                   st.session_state.schedule_minute)
        else:
            # Still time this month
            next_run = datetime(now.year, now.month, target_day,
                               st.session_state.schedule_hour,
                               st.session_state.schedule_minute)
    
    elif st.session_state.schedule_type == "custom":
        # Custom interval in minutes - simply add the custom interval to current time
        next_run = now + timedelta(minutes=st.session_state.custom_minutes)
    
    else:
        next_run = now
    
    # Log the newly calculated next run time    
    logger.info(f"Calculated next run time: {next_run}")
    return next_run

def update_schedule_interval():
    """Update the schedule interval based on the selected schedule type"""
    now = datetime.now()
    
    if st.session_state.schedule_enabled:
        if st.session_state.schedule_type == "custom":
            # For custom schedule, we directly use the configured interval in minutes
            if 'custom_minutes' not in st.session_state:
                st.session_state.custom_minutes = 60  # Default to 60 minutes
            
            # Convert minutes to milliseconds for the autorefresh component
            st.session_state.schedule_interval_ms = int(st.session_state.custom_minutes * 60 * 1000)
            
            # For custom schedules, we need a more frequent check to ensure it runs
            # But don't set it too low to avoid excessive refreshes
            # Use at most half the custom interval, but not less than 10 seconds
            check_interval_ms = min(max(10000, st.session_state.schedule_interval_ms // 2), 300000)  # between 10s and 5min
            st.session_state.schedule_interval_ms = check_interval_ms
            
            # If next_run_time is not set, initialize it
            if st.session_state.next_run_time is None:
                st.session_state.next_run_time = calculate_next_run_time()
        else:
            # For other schedule types, calculate based on next run time
            if st.session_state.next_run_time is None:
                st.session_state.next_run_time = calculate_next_run_time()
            
            time_diff = st.session_state.next_run_time - now
            
            # Convert to milliseconds for the autorefresh component
            # Use a reasonable refresh interval (not too short, not too long)
            # For long waits, refresh more frequently to avoid getting stuck
            seconds_diff = time_diff.total_seconds()
            
            if seconds_diff <= 60:  # Less than a minute away
                ms_diff = max(1000, int(seconds_diff * 1000))  # At least 1 second
            elif seconds_diff <= 3600:  # Less than an hour away
                ms_diff = min(60000, max(10000, int(seconds_diff * 1000) // 10))  # 10-60 seconds
            else:  # More than an hour away
                ms_diff = 300000  # 5 minutes
            
            st.session_state.schedule_interval_ms = ms_diff
            
        # Add a last check timestamp to detect if we're stuck
        st.session_state.last_check_time = now
    else:
        st.session_state.schedule_interval_ms = 0
        st.session_state.next_run_time = None
        if 'last_check_time' in st.session_state:
            del st.session_state.last_check_time

def toggle_schedule():
    """Toggle the schedule on/off"""
    st.session_state.schedule_enabled = not st.session_state.schedule_enabled
    if st.session_state.schedule_enabled:
        st.session_state.next_run_time = calculate_next_run_time()
        update_schedule_interval()
    
    # Save the updated configuration
    save_schedule_config()

def handle_scheduled_run(refresh_count):
    """Handle scheduled run when counter changes"""
    if not st.session_state.schedule_enabled:
        return
    
    # Check if it's time to run
    now = datetime.now()
    
    # Check if we're stuck (no updates for too long)
    if 'last_check_time' in st.session_state:
        time_since_last_check = (now - st.session_state.last_check_time).total_seconds()
        
        # If more than 10 minutes have passed since our last check, we might be stuck
        if time_since_last_check > 600:
            logger.warning(f"Scheduler may be stuck. Last check was {time_since_last_check} seconds ago. Resetting...")
            st.session_state.next_run_time = calculate_next_run_time()
            update_schedule_interval()
            st.session_state.last_check_time = now
            return
    
    # Update the last check time
    st.session_state.last_check_time = now
    
    if st.session_state.next_run_time is None:
        # Recalculate next run time if it's not set
        st.session_state.next_run_time = calculate_next_run_time()
        update_schedule_interval()
        return
    
    # Check if it's time to run the scheduled task
    if now >= st.session_state.next_run_time:
        # Signal that we need to run the fetch on the next rerun
        st.session_state.run_fetch_on_next_rerun = True
        
        # Calculate next run time
        st.session_state.next_run_time = calculate_next_run_time()
        
        # Update the schedule interval
        update_schedule_interval()
        
        # Log the scheduled execution
        logger.info(f"Scheduled run triggered at {now}. Next run at {st.session_state.next_run_time}")
        
        # Rerun to update the UI
        st.rerun()
    else:
        # Not time yet, but periodically update the interval to avoid getting stuck
        time_diff = (st.session_state.next_run_time - now).total_seconds()
        
        # Log the current status periodically to help with debugging
        if refresh_count % 5 == 0:  # Log every 5 refreshes to avoid too much logging
            logger.info(f"Waiting for next run. Current time: {now}, Next run: {st.session_state.next_run_time}, Time remaining: {time_diff} seconds")
        
        # If the schedule is custom and we're getting close to the next run time (within 10% of interval),
        # update the interval to ensure more precise timing
        if st.session_state.schedule_type == "custom" and 'custom_minutes' in st.session_state:
            custom_seconds = st.session_state.custom_minutes * 60
            if 0 < time_diff < (custom_seconds * 0.1):  # Within 10% of the interval
                update_schedule_interval()

def get_active_urls():
    """Get the active URLs based on selected checkboxes"""
    active_urls = {}
    
    for country, urls in DATA_PROVIDER_URLS.items():
        active_urls[country] = []
        for url in urls:
            source_key = get_source_key(country, url)
            if source_key in st.session_state.active_sources and st.session_state.active_sources[source_key]:
                active_urls[country].append(url)
    
    return active_urls

async def fetch_data():
    """Fetch data from sources"""
    # Get only the active URLs
    active_urls = get_active_urls()
    
    # Update fetcher with only active URLs
    st.session_state.fetcher.urls = active_urls
    
    # Add detailed fetch status logging
    all_logs = []
    files_downloaded = {}
    try:
        results, stats = await st.session_state.fetcher.fetch_links()
        # Log status for each URL
        for country, urls in active_urls.items():
            for url in urls:
                # Check if the URL was successfully fetched
                country_results = results.get(country, [])
                was_successful = any(link['base_url'] == url for link in country_results)
                status = "success" if was_successful else "failed"
                log_entry = log_fetch_status(country, url, status)
                all_logs.append(log_entry)
        
        # Download files
        files_downloaded = await st.session_state.fetcher.download_files(results)
        
        # Update last run time
        st.session_state.last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # After updating the logs, clear the cache for load_fetch_logs
        load_fetch_logs.clear()
        
        return results, stats, files_downloaded
    except Exception as e:
        # Log any unexpected errors
        for country, urls in active_urls.items():
            for url in urls:
                log_entry = log_fetch_status(country, url, "error", str(e))
                all_logs.append(log_entry)
        
        logger.error(f"Error fetching data: {str(e)}")
        
        # Clear the cache for fetch logs
        load_fetch_logs.clear()
        
        return {}, {"successful": 0, "failed": 0, "total_attempts": 0}, {}

@st.cache_data(ttl=300)  # Cache data for 5 minutes
def load_fetch_logs():
    """Load fetch logs from the status log file."""
    log_file = os.path.join('src', 'data', 'logs', 'fetch_status.json')
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
            return logs
        except:
            return []
    return []

@st.cache_data
def create_analytics_data(fetch_logs):
    """Process fetch logs into dataframes for analytics."""
    if not fetch_logs:
        return None, None
    
    # Convert logs to dataframe
    df = pd.DataFrame(fetch_logs)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Group by timestamp and count statuses
    df['date'] = df['timestamp'].dt.date
    status_counts = df.groupby(['date', 'status']).size().unstack(fill_value=0).reset_index()
    
    # Make sure all status columns exist
    for status in ['success', 'failed', 'error']:
        if status not in status_counts.columns:
            status_counts[status] = 0
    
    # Calculate success rate
    total = status_counts['success'] + status_counts['failed'] + status_counts['error']
    status_counts['success_rate'] = status_counts['success'] / total * 100
    status_counts = status_counts.sort_values('date')
    
    return status_counts, df

def save_schedule_config():
    """Save the schedule configuration to a file"""
    config_dir = os.path.join('src', 'data', 'config')
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, 'schedule_config.json')
    
    try:
        config = {
            'schedule_enabled': st.session_state.schedule_enabled,
            'schedule_type': st.session_state.schedule_type,
            'schedule_hour': st.session_state.schedule_hour,
            'schedule_minute': st.session_state.schedule_minute,
            'schedule_day': st.session_state.schedule_day,
            'schedule_weekday': st.session_state.schedule_weekday,
            'custom_minutes': st.session_state.custom_minutes,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info("Saved schedule configuration to file")
        return True
    except Exception as e:
        logger.error(f"Failed to save schedule configuration: {str(e)}")
        return False

def save_email_config():
    """Save the email configuration to a file"""
    config_dir = os.path.join('src', 'data', 'config')
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, 'email_config.json')
    
    try:
        config = {
            'email_notifications_enabled': st.session_state.email_notifications_enabled,
            'smtp_server': st.session_state.smtp_server,
            'smtp_port': st.session_state.smtp_port,
            'smtp_use_tls': st.session_state.smtp_use_tls,
            'sender_email': st.session_state.sender_email,
            'sender_password': st.session_state.sender_password,  # Note: storing password in plaintext is not secure
            'last_updated': datetime.now().isoformat()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info("Saved email configuration to file")
        return True
    except Exception as e:
        logger.error(f"Failed to save email configuration: {str(e)}")
        return False

def log_fetch_status(country, url, status, error_message=None):
    """Log fetch status to a file with date and status"""
    log_dir = os.path.join('src', 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'fetch_status.json')
    
    # Load existing logs if available
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except:
            # If file is corrupted, start with empty logs
            logs = []
    
    # Add new log entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'country': country,
        'url': url,
        'status': status,
    }
    
    if error_message:
        log_entry['error'] = error_message
    
    logs.append(log_entry)
    
    # Save logs back to file (keep only the latest 1000 entries to avoid file growth)
    with open(log_file, 'w') as f:
        json.dump(logs[-1000:], f, indent=4)
    
    logger.info(f"Logged fetch status: {status} for {country} - {url}")
    return log_entry

def toggle_email_notifications():
    """Toggle email notifications on/off"""
    st.session_state.email_notifications_enabled = not st.session_state.email_notifications_enabled
    logger.info(f"Email notifications {'enabled' if st.session_state.email_notifications_enabled else 'disabled'}")
    
    # Save the updated configuration
    save_email_config()

@st.cache_data(ttl=60)  # Cache for 1 minute
def load_file_data(file_path):
    """Load data from a file."""
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path)
        else:
            return None
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return None

def save_email_recipients():
    """Save email recipients to file for persistence"""
    email_dir = os.path.join('src', 'data', 'config')
    os.makedirs(email_dir, exist_ok=True)
    email_file = os.path.join(email_dir, 'email_recipients.json')
    
    try:
        with open(email_file, 'w') as f:
            json.dump(st.session_state.email_recipients, f)
        logger.info(f"Saved {len(st.session_state.email_recipients)} email recipients to file")
        return True
    except Exception as e:
        logger.error(f"Failed to save email recipients: {str(e)}")
        return False

def send_email_notification(subject, message, files_downloaded):
    """Send email notification to recipients when new files are downloaded"""
    if not st.session_state.email_notifications_enabled or not st.session_state.email_recipients:
        logger.info("Email notifications are disabled or no recipients configured")
        return False
    
    if not st.session_state.sender_email or not st.session_state.sender_password:
        logger.warning("Sender email or password not configured")
        return False
    
    try:
        # Apply prefix to subject
        full_subject = f"{EMAIL_CONFIG['EMAIL_SUBJECT_PREFIX']}{subject}"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['EMAIL_FROM_NAME']} <{st.session_state.sender_email}>"
        
        # Format recipients according to RFC standards for multiple recipients
        recipients = st.session_state.email_recipients.copy()
        
        # Check maximum recipients
        if len(recipients) > EMAIL_CONFIG["MAX_RECIPIENTS"]:
            logger.warning(f"Too many recipients: {len(recipients)}. Trimming to {EMAIL_CONFIG['MAX_RECIPIENTS']}")
            recipients = recipients[:EMAIL_CONFIG["MAX_RECIPIENTS"]]
        
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = full_subject
        
        # Format the email body using template
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format files list
        files_list = ""
        if files_downloaded:
            for country, files in files_downloaded.items():
                if files:
                    files_list += f"- {country}: {', '.join(files)}\n"
        
        # Use appropriate template
        email_body = EMAIL_CONFIG["TEMPLATES"]["NEW_FILES"].format(
            message=message,
            files_list=files_list if files_list else "No specific files listed",
            timestamp=timestamp
        )
        
        msg.attach(MIMEText(email_body, 'plain'))
        
        # Connect to SMTP server and send email
        server_connection = smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port)
        
        if st.session_state.smtp_use_tls:
            server_connection.starttls()
        
        server_connection.login(st.session_state.sender_email, st.session_state.sender_password)
        server_connection.send_message(msg)
        server_connection.quit()
        
        logger.info(f"Email notification sent to {len(recipients)} recipients")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def add_email_recipient():
    """Add a new email recipient to the list"""
    new_email = st.session_state.new_email_input.strip()
    if new_email and '@' in new_email and '.' in new_email:
        if new_email not in st.session_state.email_recipients:
            st.session_state.email_recipients.append(new_email)
            st.session_state.new_email_input = ""  # Clear the input
            save_email_recipients()  # Save after adding
            logger.info(f"Added email recipient: {new_email}")
        else:
            st.warning(f"Email {new_email} is already in the list")
    else:
        st.warning("Please enter a valid email address")

def add_multiple_recipients():
    """Add multiple email recipients at once"""
    if 'multiple_emails_input' in st.session_state and st.session_state.multiple_emails_input:
        # Split by commas, semicolons, or whitespace
        import re
        emails_text = st.session_state.multiple_emails_input
        potential_emails = re.split(r'[,;\s]+', emails_text)
        
        # Simple email validation and adding
        valid_count = 0
        for email in potential_emails:
            email = email.strip()
            if email and '@' in email and '.' in email:
                if email not in st.session_state.email_recipients:
                    st.session_state.email_recipients.append(email)
                    valid_count += 1
        
        if valid_count > 0:
            st.session_state.multiple_emails_input = ""  # Clear the input
            save_email_recipients()  # Save after adding
            logger.info(f"Added {valid_count} email recipients")
            return valid_count
        else:
            st.warning("No valid email addresses found")
            return 0
    return 0

def remove_email_recipient(email):
    """Remove an email recipient from the list"""
    if email in st.session_state.email_recipients:
        st.session_state.email_recipients.remove(email)
        save_email_recipients()  # Save after removing
        logger.info(f"Removed email recipient: {email}")

def clear_all_recipients():
    """Clear all email recipients"""
    if st.session_state.email_recipients:
        recipient_count = len(st.session_state.email_recipients)
        st.session_state.email_recipients = []
        save_email_recipients()
        logger.info(f"Cleared all {recipient_count} email recipients")

def test_email_configuration():
    """Send a test email to verify the configuration"""
    if not st.session_state.email_recipients:
        st.warning("Please add at least one recipient email address")
        return False
    
    if not st.session_state.sender_email or not st.session_state.sender_password:
        st.warning("Please configure sender email and password")
        return False
    
    try:
        result = send_email_notification(
            subject="Test Email",
            message="This is a test email to verify the email notification configuration is working correctly.",
            files_downloaded={}
        )
        
        if result:
            st.success("✅ Test email sent successfully!")
        else:
            st.error("❌ Failed to send test email. Check the logs for details.")
        
        return result
        
    except Exception as e:
        st.error(f"❌ Error sending test email: {str(e)}")
        return False

async def main():
    st.title('🏥 Hospital Data Fetcher')
    
    # Check if we need to run a scheduled fetch (from previous rerun)
    if st.session_state.run_fetch_on_next_rerun:
        st.session_state.run_fetch_on_next_rerun = False
        with st.status('Running scheduled data fetch...', expanded=True) as status:
            st.write('Fetching links from source websites...')
            
            # Get only the active URLs
            active_urls = get_active_urls()
            # Update fetcher with only active URLs
            st.session_state.fetcher.urls = active_urls
            
            results, stats = await st.session_state.fetcher.fetch_links()
            
            st.write(f"Found {stats['successful']} links.")
            st.write('Downloading and processing files...')
            
            downloaded = await st.session_state.fetcher.download_files(results)
            total_files = sum(len(files) for files in downloaded.values())
            
            # Display results
            if total_files > 0:
                st.write(f"Successfully downloaded {total_files} files.")
                for country, files in downloaded.items():
                    if files:
                        st.write(f"- {country}: {', '.join(files)}")
            else:
                st.write("No new files needed to be downloaded. All data is up to date.")
            
            status.update(label="Scheduled fetch completed!", state="complete")
            st.session_state.last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # For custom schedules, immediately calculate the next run time
            if st.session_state.schedule_enabled:
                st.session_state.next_run_time = calculate_next_run_time()
                update_schedule_interval()
                logger.info(f"After scheduled run, next run set to {st.session_state.next_run_time}")
    
    # Setup auto-refresh if scheduling is enabled
    if st.session_state.schedule_enabled:
        # Make sure we have a next run time
        if st.session_state.next_run_time is None:
            st.session_state.next_run_time = calculate_next_run_time()
            update_schedule_interval()
        
        # Run autorefresh with the calculated interval
        refresh_count = st_autorefresh(interval=st.session_state.schedule_interval_ms, 
                                      key='scheduler_refresh',
                                      debounce=True)
        
        # Check if the refresh count has changed
        if 'refresh_counter' not in st.session_state or refresh_count != st.session_state.refresh_counter:
            st.session_state.refresh_counter = refresh_count
            handle_scheduled_run(refresh_count)
        
        # Update the UI to show the latest next run time
        next_run_time_str = st.session_state.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        time_remaining = (st.session_state.next_run_time - datetime.now()).total_seconds()
        
        # Add a fallback refresh mechanism - if the time to next run is very small but not triggering,
        # force a rerun
        if 0 < time_remaining < 10:  # Less than 10 seconds to next run
            logger.info(f"Less than 10 seconds to next run, forcing refresh. Time remaining: {time_remaining}")
            handle_scheduled_run(refresh_count)
        
        # Add another fallback for very far future dates (potential bug)
        # If the next run time is more than a day away for custom schedules (which should run frequently)
        # or if it's in the past, reset it
        if st.session_state.schedule_type == "custom":
            if time_remaining < 0 or time_remaining > 86400:  # negative or > 1 day
                logger.warning(f"Detected invalid next run time: {st.session_state.next_run_time}. Resetting.")
                st.session_state.next_run_time = calculate_next_run_time()
                update_schedule_interval()
    
    # Reset interval if scheduling was disabled
    elif 'schedule_interval_ms' in st.session_state and st.session_state.schedule_interval_ms > 0:
        st.session_state.schedule_interval_ms = 0
        if 'next_run_time' in st.session_state:
            st.session_state.next_run_time = None
    
    # Top section with controls and stats
    controls_col1, controls_col2, controls_col3 = st.columns([2,2,3])
    
    with controls_col1:
        st.subheader('Data Fetching')
        fetch_col1, fetch_col2 = st.columns(2)
        with fetch_col1:
            fetch_btn = st.button('🔄 Fetch Now', type="primary", use_container_width=True)
        

        st.subheader('Scheduler')
        
        # Enable/disable schedule
        schedule_status = "Scheduler Enabled" if st.session_state.schedule_enabled else "Scheduler Disabled"
        schedule_color = "green" if st.session_state.schedule_enabled else "orange"
        schedule_icon = ":material/check:" if st.session_state.schedule_enabled else ":material/error:"

        st.badge(schedule_status, icon=schedule_icon, color=schedule_color)
        
        # Show next scheduled run time
        if st.session_state.schedule_enabled and st.session_state.next_run_time:
            next_run_str = st.session_state.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            st.write(f"Next scheduled run: **{next_run_str}**")
        
        # Schedule toggle button
        schedule_btn_text = f"{'Disable' if st.session_state.schedule_enabled else 'Enable'} Schedule"
        st.button(schedule_btn_text, on_click=toggle_schedule, key="schedule_toggle")
        
        # Schedule type selection
        schedule_type = st.selectbox(
            "Schedule Type",
            options=["hourly", "daily", "weekly", "monthly", "custom"],
            index=["hourly", "daily", "weekly", "monthly", "custom"].index(st.session_state.schedule_type),
            key="schedule_type_select"
        )
        st.session_state.schedule_type = schedule_type
        
        # Configure schedule parameters based on type
        if schedule_type == "hourly":
            # Define callback function
            def update_schedule_minute_hourly():
                st.session_state.schedule_minute = st.session_state.schedule_minute_hourly
                
            st.number_input("Minute (0-59)", 
                          min_value=0, 
                          max_value=59, 
                          value=st.session_state.schedule_minute,
                          on_change=update_schedule_minute_hourly,
                          key="schedule_minute_hourly")
            
        elif schedule_type == "daily":
            # Define callback functions
            def update_schedule_hour_daily():
                st.session_state.schedule_hour = st.session_state.schedule_hour_daily
                
            def update_schedule_minute_daily():
                st.session_state.schedule_minute = st.session_state.schedule_minute_daily
                
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Hour (0-23)", 
                              min_value=0, 
                              max_value=23,
                              value=st.session_state.schedule_hour,
                              on_change=update_schedule_hour_daily,
                              key="schedule_hour_daily")
            with col2:
                st.number_input("Minute (0-59)", 
                              min_value=0, 
                              max_value=59,
                              value=st.session_state.schedule_minute,
                              on_change=update_schedule_minute_daily,
                              key="schedule_minute_daily")
            
        elif schedule_type == "weekly":
            # Define callback functions
            def update_schedule_hour_weekly():
                st.session_state.schedule_hour = st.session_state.schedule_hour_weekly
                
            def update_schedule_minute_weekly():
                st.session_state.schedule_minute = st.session_state.schedule_minute_weekly
                
            weekday_options = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            selected_weekday = st.selectbox("Day of Week", 
                                          options=weekday_options,
                                          index=st.session_state.schedule_weekday,
                                          key="weekday_select")
            st.session_state.schedule_weekday = weekday_options.index(selected_weekday)
            
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Hour (0-23)", 
                              min_value=0, 
                              max_value=23,
                              value=st.session_state.schedule_hour,
                              on_change=update_schedule_hour_weekly,
                              key="schedule_hour_weekly")
            with col2:
                st.number_input("Minute (0-59)", 
                              min_value=0, 
                              max_value=59,
                              value=st.session_state.schedule_minute,
                              on_change=update_schedule_minute_weekly,
                              key="schedule_minute_weekly")
            
        elif schedule_type == "monthly":
            # Define callback functions
            def update_schedule_day():
                st.session_state.schedule_day = st.session_state.schedule_day_monthly
                
            def update_schedule_hour_monthly():
                st.session_state.schedule_hour = st.session_state.schedule_hour_monthly
                
            def update_schedule_minute_monthly():
                st.session_state.schedule_minute = st.session_state.schedule_minute_monthly
                
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Day of Month (1-28)", 
                              min_value=1, 
                              max_value=28,
                              value=st.session_state.schedule_day,
                              on_change=update_schedule_day,
                              key="schedule_day_monthly")
            
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Hour (0-23)", 
                              min_value=0, 
                              max_value=23,
                              value=st.session_state.schedule_hour,
                              on_change=update_schedule_hour_monthly,
                              key="schedule_hour_monthly")
            with col2:
                st.number_input("Minute (0-59)", 
                              min_value=0, 
                              max_value=59,
                              value=st.session_state.schedule_minute,
                              on_change=update_schedule_minute_monthly,
                              key="schedule_minute_monthly")
            
        elif schedule_type == "custom":
            # Define callback function
            def update_custom_minutes():
                st.session_state.custom_minutes = st.session_state.custom_minutes_input
                
            st.number_input("Run every X minutes", 
                          min_value=1, 
                          max_value=10080,  # 7 days in minutes
                          value=st.session_state.custom_minutes,
                          on_change=update_custom_minutes,
                          key="custom_minutes_input")
        
        # Update button
        if st.button("Update Schedule"):
            st.session_state.next_run_time = calculate_next_run_time()
            update_schedule_interval()
            save_schedule_config()  # Save the updated schedule configuration
            if st.session_state.next_run_time:
                st.success(f"Schedule updated! Next run at {st.session_state.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.success("Schedule updated!")
            st.rerun()
    
    with controls_col2:
        st.subheader('Data Sources')
        
        # Show available data sources with toggles
        for country, urls in DATA_PROVIDER_URLS.items():
            st.write(f"**{country}**")
            for url in urls:
                if "public-hospitals" in url:
                    label = "Public Hospitals"
                elif "private-hospitals" in url:
                    label = "Private Hospitals"
                elif "declared-hospitals" in url:
                    label = "Declared Hospitals"
                else:
                    label = url.split('/')[-1]
                
                source_key = get_source_key(country, url)
                # Use the source_key for the checkbox
                st.session_state.active_sources[source_key] = st.checkbox(
                    label, 
                    value=st.session_state.active_sources.get(source_key, True),
                    key=f"source_{source_key}"
                )
                
    with controls_col3:
        st.subheader('Status')
        fetch_logs = load_fetch_logs()
        
        status_cols = st.columns(3)
        with status_cols[0]:
            if fetch_logs:
                last_run = fetch_logs[-1]
                # Modified to handle missing 'total_attempts' key
                if 'total_attempts' in last_run:
                    success_rate = (last_run['successful'] / last_run['total_attempts'] * 100) if last_run['total_attempts'] > 0 else 0
                else:
                    # If fetch_status.json entries don't have total_attempts, use the status column
                    success_count = sum(1 for log in fetch_logs if log.get('status') == 'success')
                    total_count = len(fetch_logs)
                    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
                st.metric('Success Rate', f"{success_rate:.1f}%")
            else:
                st.metric('Success Rate', 'N/A')
                
        with status_cols[1]:
            if fetch_logs:
                # Modified to handle missing 'successful' key
                if 'successful' in last_run:
                    st.metric('Files Downloaded', last_run['successful'])
                else:
                    success_count = sum(1 for log in fetch_logs if log.get('status') == 'success')
                    st.metric('Files Downloaded', success_count)
                # If we don't have a last_run_time from session state, use the one from fetch logs
                if not st.session_state.last_run_time:
                    st.session_state.last_run_time = pd.to_datetime(last_run['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            else:
                st.metric('Files Downloaded', 'N/A')


        ################
        status_cols1 = st.columns(2)                
        with status_cols1[0]:
            if st.session_state.last_run_time:
                # Convert last_run_time to datetime if it's a string
                if isinstance(st.session_state.last_run_time, str):
                    last_run_datetime = datetime.strptime(st.session_state.last_run_time, '%Y-%m-%d %H:%M:%S')
                else:
                    last_run_datetime = st.session_state.last_run_time
                
                # Format as simple date and time
                formatted_time = last_run_datetime.strftime('%b %d, %H:%M:%S')
                
                # Show both formatted and full time (in tooltip)
                st.metric('Last Run', formatted_time, help=st.session_state.last_run_time)
            else:
                st.metric('Last Run', 'Never')
        ###############

        
        
        # Progress bar for running manual fetch
        if fetch_btn:
            with st.status('Running data fetch...', expanded=True) as status:
                # Get only the active URLs
                active_urls = get_active_urls()
                # Update fetcher with only active URLs
                active_data_source = st.session_state.fetcher.urls = active_urls
                get_links = [url for country_urls in active_data_source.values() for url in country_urls]


                st.write(f'Fetching links from source websites... {get_links}',)
                
                
                results, stats, downloaded = await fetch_data()
                
                st.write(f"Found {stats['successful']} links.")
                st.write('Downloading and processing files...')
                
                total_files = sum(len(files) for files in downloaded.values())
                
                # Display results
                if total_files > 0:
                    st.write(f"Successfully downloaded {total_files} files.")
                    for country, files in downloaded.items():
                        if files:
                            st.write(f"- {country}: {', '.join(files)}")
                    
                    # Clear the analytics data cache
                    create_analytics_data.clear()
                else:
                    st.write("No new files needed to be downloaded. All data is up to date.")
                
                status.update(label="Fetch completed!", state="complete")
                st.session_state.last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Force a rerun to update the analytics
                st.rerun()

    tab1, tab2, tab3 = st.tabs(["📊 Analytics", "📁 Downloaded Files", "⚙️ Settings"])
    with tab1:
        status_counts, log_df = create_analytics_data(fetch_logs)
        
        if status_counts is not None and not status_counts.empty:
            chart_cols = st.columns(2)
            
            with chart_cols[0]:
                st.subheader('Fetch Success Rate')
                st.line_chart(
                    status_counts, 
                    x='date', 
                    y='success_rate',
                    color=None  # Single line
                )
            
            with chart_cols[1]:
                st.subheader('Fetch Attempts')
                st.bar_chart(
                    status_counts,
                    x='date',
                    y=['success', 'failed', 'error']
                )
                
            # Add a table with recent fetch activity
            st.subheader("Recent Fetch Activity")
            if log_df is not None and not log_df.empty:
                # Show last 10 fetch activities
                recent_logs = log_df.sort_values('timestamp', ascending=False).head(10)
                recent_logs['time'] = recent_logs['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(
                    recent_logs[['time', 'country', 'status', 'url']],
                    use_container_width=True,
                    height=250,  # Added fixed height to make it scrollable
                    column_config={
                        'time': 'Time',
                        'country': 'Country',
                        'status': st.column_config.SelectboxColumn(
                            'Status',
                            help='Fetch status',
                            options=['success', 'failed', 'error'],
                            required=True,
                        ),
                        'url': 'URL'
                    }
                )
        else:
            st.info('No fetch history available yet. Run a fetch to see analytics.')
    
    with tab2:
        download_dir = os.path.join('src', 'data', 'downloads')
        if os.path.exists(download_dir):
            files = os.listdir(download_dir)
            if files:
                # Group files by country
                files_by_country = {}
                for file in files:
                    country = file.split('_')[0] if '_' in file else 'Other'
                    if country not in files_by_country:
                        files_by_country[country] = []
                    files_by_country[country].append(file)
                
                # Create tabs for each country
                country_tabs = st.tabs(list(files_by_country.keys()))
                for tab, country in zip(country_tabs, files_by_country.keys()):
                    with tab:
                        st.subheader(f"{country} Files")
                        
                        # Add statistics section for AU tab
                        if country == "AU":
                            st.write("#### Hospital Type Distribution")
                            
                            # Create a container for the statistics
                            stats_container = st.container()
                            
                            # We'll populate this once a file is selected
                        
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            selected_file = st.selectbox(
                                f"Select a file", 
                                files_by_country[country],
                                key=f"file_selector_{country}"
                            )
                            
                            if selected_file:
                                file_path = os.path.join(download_dir, selected_file)
                                file_stats = os.stat(file_path)
                                file_size_kb = file_stats.st_size / 1024
                                file_modified = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                                
                                st.write(f"**Size:** {file_size_kb:.1f} KB")
                                st.write(f"**Modified:** {file_modified}")
                                
                                df = load_file_data(file_path)
                                if df is not None:
                                    # Show hospital type distribution for AU
                                    if country == "AU" and not df.empty and len(df.columns) > 0:
                                        first_col = df.columns[0]
                                        
                                        # Count PRIVATE and PUBLIC values in the first column
                                        type_counts = df[first_col].value_counts()
                                        private_count = type_counts.get("PRIVATE", 0)
                                        public_count = type_counts.get("PUBLIC", 0)
                                        other_count = len(df) - private_count - public_count
                                        
                                        # Show counts in the stats container
                                        with stats_container:
                                            stat_cols = st.columns(3)
                                            with stat_cols[0]:
                                                st.metric("Private Hospitals", private_count)
                                                st.progress(private_count / len(df))
                                            with stat_cols[1]:
                                                st.metric("Public Hospitals", public_count)
                                                st.progress(public_count / len(df))
                                            if other_count > 0:
                                                with stat_cols[2]:
                                                    st.metric("Other Types", other_count)
                                                    st.progress(other_count / len(df))
                                            
                                            # Add a pie chart to visualize distribution
                                            if private_count > 0 or public_count > 0:
                                                fig = go.Figure(data=[
                                                    go.Pie(
                                                        labels=["Private", "Public", "Other"] if other_count > 0 else ["Private", "Public"],
                                                        values=[private_count, public_count, other_count] if other_count > 0 else [private_count, public_count],
                                                        marker=dict(colors=['#ff9c34', '#0068c9', '#808080'] if other_count > 0 else ['#ff9c34', '#0068c9'])
                                                    )
                                                ])
                                                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200)
                                                st.plotly_chart(fig, use_container_width=True)
                                    
                                    st.download_button(
                                        "⬇️ Download file",
                                        df.to_csv(index=False).encode('utf-8'),
                                        selected_file,
                                        f"text/csv",
                                        key=f'download_{country}',
                                        use_container_width=True
                                    )
                        
                        with col2:
                            if selected_file:
                                df = load_file_data(file_path)
                                if df is not None:
                                    st.dataframe(df, use_container_width=True, height=400)
            else:
                st.info("No downloaded files available.")
        else:
            st.info("Download directory not found. Please run a fetch first.")
    
    with tab3:
    # Email notification settings
        st.subheader('Email Notifications')
        
        # Email notification toggle
        notification_status = "Notifications Enabled" if st.session_state.email_notifications_enabled else "Notifications Disabled"
        notification_color = "green" if st.session_state.email_notifications_enabled else "gray"
        notification_icon = "✉️" if st.session_state.email_notifications_enabled else "✉"
        
        st.badge(notification_status, icon=notification_icon, color=notification_color)
        
        # Toggle button
        notification_btn_text = f"{'Disable' if st.session_state.email_notifications_enabled else 'Enable'} Notifications"
        st.button(notification_btn_text, on_click=toggle_email_notifications, key="notification_toggle")
        
        # Email notification settings
        with st.expander("Email Server Configuration"):
            # Define callback functions to update session state
            def update_sender_email():
                if 'sender_email_input' in st.session_state:
                    st.session_state.sender_email = st.session_state.sender_email_input
                    save_email_config()  # Save the updated email configuration
                    
            def update_sender_password():
                if 'sender_password_input' in st.session_state:
                    st.session_state.sender_password = st.session_state.sender_password_input
                    save_email_config()  # Save the updated email configuration
                    
            def update_smtp_server():
                if 'smtp_server_input' in st.session_state:
                    st.session_state.smtp_server = st.session_state.smtp_server_input
                    save_email_config()  # Save the updated email configuration
                    
            def update_smtp_port():
                if 'smtp_port_input' in st.session_state:
                    st.session_state.smtp_port = st.session_state.smtp_port_input
                    save_email_config()  # Save the updated email configuration
                    
            def update_smtp_use_tls():
                if 'smtp_use_tls_input' in st.session_state:
                    st.session_state.smtp_use_tls = st.session_state.smtp_use_tls_input
                    save_email_config()  # Save the updated email configuration
            
            # Use separate keys for inputs, which will update session state via callbacks
            st.text_input("Sender Email", 
                        value=st.session_state.sender_email,
                        placeholder="your-email@example.com",
                        key="sender_email_input",
                        on_change=update_sender_email)
            
            st.text_input("Email Password/App Password", 
                        value=st.session_state.sender_password,
                        type="password",
                        help="For Gmail, you need to use an App Password",
                        key="sender_password_input",
                        on_change=update_sender_password)
            
            server_col1, server_col2, server_col3 = st.columns([2, 1, 1])
            with server_col1:
                st.text_input("SMTP Server", 
                            value=st.session_state.smtp_server,
                            key="smtp_server_input",
                            on_change=update_smtp_server)
            with server_col2:
                st.number_input("SMTP Port", 
                            value=st.session_state.smtp_port,
                            min_value=1,
                            max_value=65535,
                            key="smtp_port_input",
                            on_change=update_smtp_port)
            with server_col3:
                st.checkbox("Use TLS", 
                        value=st.session_state.smtp_use_tls,
                        key="smtp_use_tls_input",
                        on_change=update_smtp_use_tls)
            
            # Initialize input values if they don't exist yet
            for key in ["sender_email_input", "sender_password_input", "smtp_server_input", "smtp_port_input", "smtp_use_tls_input"]:
                if key not in st.session_state:
                    base_key = key.replace("_input", "")
                    if base_key in st.session_state:
                        st.session_state[key] = st.session_state[base_key]
            
            # Test configuration button
            st.button("Test Email Configuration", on_click=test_email_configuration, key="test_email_btn")
        
        # Email recipients management
        with st.expander("Email Recipients", expanded=True):
            # Single recipient entry
            st.text_input("Add Single Recipient", 
                        placeholder="email@example.com",
                        key="new_email_input")
            
            st.button("Add Recipient", on_click=add_email_recipient, key="add_email_btn")
            
            # Multiple recipients entry
            st.text_area("Add Multiple Recipients", 
                        placeholder="Enter multiple email addresses separated by commas, semicolons, or newlines",
                        height=100,
                        key="multiple_emails_input")
            
            st.button("Add Multiple Recipients", on_click=add_multiple_recipients, key="add_multiple_btn")
            
            # Show current recipients with count
            recipient_count = len(st.session_state.email_recipients)
            if recipient_count > 0:
                st.write(f"**Current Recipients ({recipient_count}):**")
                
                # Display recipients in a scrollable container if there are many
                with st.container(height=180 if recipient_count > 4 else None):
                    for idx, email in enumerate(st.session_state.email_recipients):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.text(email)
                        with col2:
                            st.button("🗑️", key=f"remove_{idx}", on_click=remove_email_recipient, args=(email,), help="Remove this recipient")
                
                # Clear all button
                st.button("Clear All Recipients", on_click=clear_all_recipients, key="clear_all_btn")

    # Footer with information
    st.markdown("---")
    st.caption("Hospital Data Fetcher v1.0 | Data from health.govt.nz & health.gov.au")

if __name__ == "__main__":
    # Run the async app
    asyncio.run(main()) 