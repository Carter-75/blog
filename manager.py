import argparse
import logging
import json
import os

from utils import get_config, get_post_history, save_post_history
from site_deployer import update_index_page, delete_from_disk, list_html_files_on_disk

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
    """Deletes a post from disk and the local history, then rebuilds the index."""
    logging.info(f"Starting deletion process for '{filename_to_delete}'...")
    
    web_app_path = config.get('web_app_path', '~/MoneyScript/webapp') # Example path
    history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')
    
    # 1. Delete from disk
    disk_deleted = delete_from_disk(filename_to_delete, os.path.expanduser(web_app_path))
    if not disk_deleted:
        logging.error("Halting process because disk deletion failed.")
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
        updated_history = get_post_history(history_file)
        update_index_page(updated_history, os.path.expanduser(web_app_path), template_html)
        logging.info("Index page has been successfully rebuilt.")
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot rebuild the index page.")
    except Exception as e:
        logging.error(f"An error occurred while rebuilding the index page: {e}")

    logging.info(f"Deletion process for '{filename_to_delete}' completed successfully.")


def delete_all_posts(config):
    """
    Finds all HTML files on disk and deletes them after user confirmation.
    """
    web_app_path = config.get('web_app_path', '~/MoneyScript/webapp')
    history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')

    # 1. Get the list of files directly from the disk
    logging.info("Getting the list of published articles directly from the web app directory...")
    all_html_files = list_html_files_on_disk(os.path.expanduser(web_app_path))

    if all_html_files is None:
        logging.error("Could not retrieve file list from disk. Aborting.")
        return

    # 2. Filter out essential files
    files_to_delete = [
        f for f in all_html_files 
        if f not in ['index.html', 'disclosure.html']
    ]

    if not files_to_delete:
        logging.info("No articles found on the server to delete.")
        return

    # 3. Ask for user confirmation
    print("\n--- Articles Found on Server ---")
    for filename in files_to_delete:
        print(f"- {filename}")
    print("--------------------------------")
    
    logging.warning(f"You are about to delete all {len(files_to_delete)} articles from your server.")
    confirm = input("This action CANNOT be undone. Are you sure? (type 'yes' to confirm): ")

    if confirm.lower() != 'yes':
        logging.info("Deletion cancelled by user.")
        return

    logging.info("User confirmed. Proceeding with deletion of all posts...")
    
    # 4. Delete all the files from disk
    all_deleted_successfully = True
    for filename in files_to_delete:
        if not delete_from_disk(filename, os.path.expanduser(web_app_path)):
            all_deleted_successfully = False
            logging.error(f"Failed to delete {filename}. Stopping to prevent further issues.")
            break # Stop if any deletion fails
    
    if not all_deleted_successfully:
        logging.error("Some files could not be deleted. The local history will not be cleared. Please check the server manually.")
        return

    # 5. Clear the local history file
    logging.info("Clearing local post history...")
    save_post_history(history_file, []) # Save an empty list
        
    # 6. Rebuild and deploy a now-empty index.html
    logging.info("Rebuilding and deploying empty index page...")
    try:
        with open('template.html', 'r', encoding='utf-8') as f:
            template_html = f.read()
        update_index_page([], os.path.expanduser(web_app_path), template_html)
        logging.info("Empty index page has been successfully deployed.")
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot rebuild the index page.")
    
    logging.info("All posts have been successfully deleted from the server.")


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