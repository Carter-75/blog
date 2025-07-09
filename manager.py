import argparse
import logging
import json
import os

from utils import get_config, get_post_history
from site_deployer import update_index_page, delete_from_ftp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def list_posts(history_file):
    """Prints a formatted list of all posts from the history file."""
    logging.info("Fetching post history...")
    history = get_post_history(history_file)
    if not history:
        logging.info("No posts found in history.")
        return
    
    print("\n--- Published Articles ---")
    for i, post in enumerate(history, 1):
        title = post.get('title', 'N/A')
        filename = post.get('filename', 'N/A')
        timestamp = post.get('timestamp', 'N/A').strftime('%Y-%m-%d %H:%M')
        print(f"{i}. Title: {title}\n   File:  {filename}\n   Date:  {timestamp}\n")
    print("------------------------\n")

def delete_post(filename_to_delete, config):
    """Deletes a post from FTP and the local history, then rebuilds the index."""
    logging.info(f"Starting deletion process for '{filename_to_delete}'...")
    
    history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')
    
    # 1. Delete from FTP server
    ftp_deleted = delete_from_ftp(filename_to_delete, config['ftp'])
    if not ftp_deleted:
        logging.error("Halting process because FTP deletion failed.")
        return

    # 2. Update local history file
    logging.info("Updating local post history...")
    history = get_post_history(history_file)
    new_history = [post for post in history if post.get('filename') != filename_to_delete]

    if len(new_history) == len(history):
        logging.warning(f"Did not find '{filename_to_delete}' in the history file. Rebuilding index anyway.")
    
    try:
        with open(history_file, 'w') as f:
            for record in new_history:
                # Timestamps are datetime objects, convert back to string for JSON
                record['timestamp'] = record['timestamp'].isoformat()
                f.write(json.dumps(record) + '\n')
        logging.info("Successfully updated post history file.")
    except IOError as e:
        logging.error(f"Failed to write updated history file: {e}")
        return

    # 3. Rebuild and deploy the main index.html
    logging.info("Rebuilding and deploying the main index page...")
    try:
        with open('template.html', 'r', encoding='utf-8') as f:
            template_html = f.read()
        # We need to get the history again, since we just overwrote it
        updated_history = get_post_history(history_file)
        update_index_page(updated_history, config.get('ftp'), template_html)
        logging.info("Index page has been successfully rebuilt.")
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot rebuild the index page.")
    except Exception as e:
        logging.error(f"An error occurred while rebuilding the index page: {e}")

    logging.info(f"Deletion process for '{filename_to_delete}' completed successfully.")


def delete_all_posts(config):
    """Deletes ALL posts from FTP and local history after user confirmation."""
    history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')
    history = get_post_history(history_file)

    if not history:
        logging.info("No posts found in history. Nothing to delete.")
        return

    logging.warning(f"You are about to delete all {len(history)} posts from your server and local history.")
    confirm = input("This action CANNOT be undone. Are you sure you want to continue? (type 'yes' to confirm): ")

    if confirm.lower() != 'yes':
        logging.info("Deletion cancelled by user.")
        return

    logging.info("User confirmed. Proceeding with deletion of all posts...")
    
    # 1. Delete all files from FTP
    for post in history:
        filename = post.get('filename')
        if filename:
            delete_from_ftp(filename, config['ftp'])
    
    # 2. Clear the local history file
    try:
        with open(history_file, 'w') as f:
            f.write('')
        logging.info("Successfully cleared local post history.")
    except IOError as e:
        logging.error(f"Failed to clear history file: {e}")
        return
        
    # 3. Rebuild and deploy a now-empty index.html
    logging.info("Rebuilding and deploying empty index page...")
    try:
        with open('template.html', 'r', encoding='utf-8') as f:
            template_html = f.read()
        # Pass an empty history to build an empty index
        update_index_page([], config.get('ftp'), template_html)
        logging.info("Empty index page has been successfully deployed.")
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot rebuild the index page.")
    
    logging.info("All posts have been successfully deleted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Management tool for the Automated Blog Empire.")
    parser.add_argument('--list', action='store_true', help='List all published articles.')
    parser.add_argument('--delete', type=str, help='Delete an article by its filename.')
    parser.add_argument('--delete-all', action='store_true', help='Delete ALL articles from the server and local history.')
    
    args = parser.parse_args()
    
    config = get_config()
    if not config:
        logging.critical("Cannot operate without a valid config.json file.")
    else:
        history_file_path = config.get('throttling', {}).get('post_history_file', 'post_history.log')

        if args.list:
            list_posts(history_file_path)
        elif args.delete:
            delete_post(args.delete, config)
        elif args.delete_all:
            delete_all_posts(config)
        else:
            parser.print_help() 