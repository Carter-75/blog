import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import os

def get_config():
    """Loads the main configuration file."""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("FATAL: config.json not found. Please ensure the file exists.")
        return None
    except json.JSONDecodeError:
        logging.error("FATAL: config.json is not a valid JSON file. Please check its syntax.")
        return None

def get_post_history(history_file):
    """Reads the post history records from its file."""
    if not os.path.exists(history_file):
        return []
    try:
        with open(history_file, 'r') as f:
            records = []
            for line in f:
                if line.strip():
                    try:
                        # For backward compatibility, handle old timestamp-only format
                        if '{' not in line:
                            records.append({'timestamp': datetime.fromisoformat(line.strip())})
                        else:
                            record = json.loads(line)
                            record['timestamp'] = datetime.fromisoformat(record['timestamp'])
                            records.append(record)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logging.warning(f"Skipping malformed line in post history: {line.strip()} - Error: {e}")
            return records
    except IOError as e:
        logging.error(f"Could not read post history file {history_file}: {e}")
        return []

def add_to_post_history(history_file, filename, title):
    """Adds a new post record to the history file."""
    record = {
        'timestamp': datetime.now().isoformat(),
        'filename': filename,
        'title': title
    }
    try:
        with open(history_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
    except IOError as e:
        logging.error(f"Failed to write to post history file {history_file}: {e}")

def save_post_history(history_file, history_records):
    """
    Overwrites the history file with a new set of records.

    Args:
        history_file (str): The path to the history file.
        history_records (list): The list of history records to save.
    """
    try:
        with open(history_file, 'w') as f:
            for record in history_records:
                # Make a copy to avoid modifying the original list
                record_to_save = record.copy()
                # Ensure timestamp is in ISO format string for JSON
                if isinstance(record_to_save.get('timestamp'), datetime):
                    record_to_save['timestamp'] = record_to_save['timestamp'].isoformat()
                f.write(json.dumps(record_to_save) + '\n')
    except IOError as e:
        logging.error(f"Failed to save post history file {history_file}: {e}")

def extract_title_from_html(html_content):
    """Extracts the text from the first <h2> tag in the HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        h2 = soup.find('h2')
        return h2.get_text(strip=True) if h2 else None
    except Exception as e:
        logging.error(f"Error extracting title from HTML: {e}")
        return None

def extract_first_paragraph(html_content):
    """Extracts the text from the first <p> tag in the HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        p = soup.find('p')
        return p.get_text(strip=True) if p else None
    except Exception as e:
        logging.error(f"Error extracting first paragraph from HTML: {e}")
        return None

def sanitize_filename(text):
    """
    Cleans a string to be a safe, valid filename.
    Removes special characters, limits length, and replaces spaces.
    """
    import re
    # Remove non-alphanumeric characters except for spaces and hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    # Collapse consecutive hyphens
    text = re.sub(r'--+', '-', text)
    # Trim leading/trailing hyphens
    text = text.strip('-')
    # Limit length to 50 chars to be safe
    return text.lower()[:50] 