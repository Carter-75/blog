import json
import logging
import time
from datetime import datetime, timedelta
import random
import sys # Import sys to read command-line arguments
import os

# Import your project modules
from content_generator import generate_content
from affiliate_link_inserter import insert_affiliate_links
from site_deployer import deploy_to_disk, update_index_page, delete_from_disk
from social_poster import post_to_reddit
from utils import get_config, get_post_history, add_to_post_history, save_post_history, extract_title_from_html, sanitize_filename

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main_loop():
    """
    Main operational loop for the automated blog empire.
    """
    logging.info("Starting a new cycle in the main loop.")
    
    config = get_config()
    if not config:
        return # Stop if config is invalid

    # --- Step 1: Select a Product from the Curated Portfolio ---
    product_portfolio = config.get('product_portfolio', [])
    if not product_portfolio:
        logging.error("The 'product_portfolio' in config.json is empty. Cannot proceed.")
        return
        
    product_info = random.choice(product_portfolio)
    logging.info(f"Selected product '{product_info.get('title')}' from the portfolio.")

    # --- Step 2: Generate Content Based on the Product ---
    article_html = generate_content(product_info, config.get('content_provider'))
    if not article_html:
        logging.error("Failed to generate content. Skipping this cycle.")
        # We still run the cleanup logic even on failure
    else:
        # --- Step 3: Insert the Affiliate Link ---
        final_html = insert_affiliate_links(article_html, product_info)
        
        # Extract a clean title for the filename and social post
        article_title = extract_title_from_html(final_html)
        if not article_title:
            logging.warning("Could not extract title from generated HTML. Using a generic title.")
            article_title = product_info['title'] # Fallback to product title

        # ---=== Cache-Busting ===---
        cache_buster = str(int(time.time()))
        final_html = final_html.replace('{{CACHE_BUSTER}}', cache_buster)
        
        # --- Step 4: Deploy the New Post to the Website ---
        filename = f"{sanitize_filename(article_title)}.html"
        web_app_path = config.get('web_app_path', '~/MoneyScript/webapp') # Example path
        
        success = deploy_to_disk(filename, final_html, os.path.expanduser(web_app_path))
        if success:
            # Add to history ONLY on successful deployment
            history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')
            post_history = get_post_history(history_file)
            new_record = {
                'timestamp': datetime.now(),
                'filename': filename,
                'title': article_title,
                'product_link': product_info['link']
            }
            post_history.append(new_record)
            save_post_history(history_file, post_history)
            logging.info(f"Successfully posted '{filename}' and updated history.")

            # --- Step 5: Promote on Social Media (only on success) ---
            reddit_config = config.get('social_posting', {}).get('reddit', {})
            if reddit_config.get('enabled'):
                site_url = config.get('site_url')
                if not site_url or 'YOUR_SITE_URL' in site_url:
                    logging.warning("Site URL is not configured. Cannot post to social media.")
                else:
                    reddit_config['site_url'] = site_url
                    post_url = f"{site_url.rstrip('/')}/{filename}"
                    post_to_reddit(reddit_config, article_title, post_url, final_html)
    
    # --- Step 6: Site-wide Cleanup and Index Rebuild ---
    # This runs every cycle, regardless of whether a post succeeded or failed.
    logging.info("Starting site-wide cleanup and index rebuild...")
    history_file = config.get('throttling', {}).get('post_history_file', 'post_history.log')
    post_history = get_post_history(history_file)
    
    # Post-rotation logic for ALL products
    MAX_POSTS_PER_PRODUCT = 2
    all_products_in_portfolio = config.get('product_portfolio', [])

    if all_products_in_portfolio:
        for product_in_portfolio in all_products_in_portfolio:
            product_link = product_in_portfolio['link']
            product_posts = [p for p in post_history if p.get('product_link') == product_link]
            
            if len(product_posts) > MAX_POSTS_PER_PRODUCT:
                product_posts.sort(key=lambda x: x['timestamp'])
                num_to_delete = len(product_posts) - MAX_POSTS_PER_PRODUCT
                posts_to_delete = product_posts[:num_to_delete]
                
                logging.info(f"Cleanup triggered for product link '{product_link}'. Found {len(product_posts)} posts, max is {MAX_POSTS_PER_PRODUCT}. Deleting {num_to_delete} oldest post(s).")
                for post in posts_to_delete:
                    if delete_from_disk(post['filename'], os.path.expanduser(web_app_path)):
                        post_history = [p for p in post_history if p.get('filename') != post.get('filename')]
                    else:
                        logging.error(f"Failed to delete '{post['filename']}' from disk. It will remain in history. Aborting rotation for this product.")
                        break
        
        save_post_history(history_file, post_history)
    
    # Update the main index page based on the final, cleaned history
    web_app_path = config.get('web_app_path', '~/MoneyScript/webapp')
    try:
        with open('template.html', 'r', encoding='utf-8') as f:
            template_html = f.read()
        update_index_page(post_history, os.path.expanduser(web_app_path), template_html)
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot update the index page.")
    except Exception as e:
        logging.error(f"An error occurred while updating the index page: {e}")

    # Also ensure core files are present
    try:
        logging.info("Ensuring core site files (CSS, disclosure) are uploaded...")
        with open('style.css', 'r', encoding='utf-8') as f:
            deploy_to_disk('style.css', f.read(), os.path.expanduser(web_app_path))
        with open('disclosure.html', 'r', encoding='utf-8') as f:
            deploy_to_disk('disclosure.html', f.read(), os.path.expanduser(web_app_path))
    except FileNotFoundError as e:
        logging.warning(f"{e.filename} not found locally. Skipping its upload.")
    except Exception as e:
        logging.error(f"An error occurred while uploading core files: {e}")

    logging.info("Cycle complete. Waiting for next opportunity.")


def is_time_to_post(throttling_config):
    """
    Checks if enough time has passed to make a new post based on throttling rules.
    """
    history_file = throttling_config.get('post_history_file', 'post_history.log')
    min_delay_minutes = throttling_config.get('min_delay_between_posts_minutes', 240)
    max_posts_24h = throttling_config.get('max_posts_per_24_hours', 4)

    history = get_post_history(history_file)
    now = datetime.now()

    # 1. Check if the minimum delay has passed since the last post
    if history:
        last_post_time = history[-1]['timestamp'] # Access timestamp from record
        if now < last_post_time + timedelta(minutes=min_delay_minutes):
            logging.info(f"Waiting for min delay. Last post was at {last_post_time}. Next post possible after {last_post_time + timedelta(minutes=min_delay_minutes)}.")
            return False

    # 2. Check if we have exceeded the max posts in the last 24 hours
    posts_in_last_24h = [record['timestamp'] for record in history if now - record['timestamp'] < timedelta(hours=24)]
    if len(posts_in_last_24h) >= max_posts_24h:
        logging.info(f"Max posts per 24h reached ({len(posts_in_last_24h)}/{max_posts_24h}). Waiting.")
        return False

    return True

if __name__ == "__main__":
    logging.info("Automated Blog Empire Runner started.")
    logging.info("The system will now run continuously, checking for opportunities to post.")
    
    # Check for the override flag, e.g., 'python runner.py -o'
    override_throttling = '-o' in sys.argv

    if override_throttling:
        logging.warning("Time limit override flag '-o' detected. The script will post immediately and run only once.")
        main_loop()
    else:
        while True:
            try:
                config = get_config()
                if not config:
                    logging.error("Halting due to missing or invalid config file.")
                    time.sleep(60)
                    continue
                
                throttling_config = config.get('throttling', {})
                
                if is_time_to_post(throttling_config):
                    main_loop()
                
                # Sleep for a set interval regardless of whether a post was made.
                # This is the main loop's "tick" rate.
                logging.info("Loop finished. Sleeping for 10 minutes before next check.")
                time.sleep(600)

            except KeyboardInterrupt:
                logging.info("Script manually interrupted by user. Shutting down.")
                break
            except Exception as e:
                logging.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)
                logging.info("Restarting loop after a delay to prevent crash loops.")
                time.sleep(3600) # Sleep for 1 hour on critical failure