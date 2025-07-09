import logging
import io
import time
import os

def deploy_to_disk(filename, content, web_app_path):
    """
    Saves a file's content to a local path, for direct hosting.

    Args:
        filename (str): The name for the file.
        content (str): The content of the file to be saved.
        web_app_path (str): The full path to the web app's directory.

    Returns:
        bool: True if the save was successful, False otherwise.
    """
    try:
        if not os.path.exists(web_app_path):
            os.makedirs(web_app_path)
            logging.info(f"Created web app directory: {web_app_path}")
            
        full_path = os.path.join(web_app_path, filename)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logging.info(f"Successfully saved {filename} to {full_path}.")
        return True

    except IOError as e:
        logging.error(f"An I/O error occurred while saving {filename}: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during disk deployment: {e}")
        return False

def update_index_page(post_history, web_app_path, template_html):
    """
    Generates and saves an index.html file with a list of all posts.
    """
    logging.info("Generating and saving site index page...")
    
    sorted_posts = sorted(
        [p for p in post_history if 'filename' in p],
        key=lambda x: x['timestamp'], 
        reverse=True
    )

    post_links_html = '<ul class="post-grid">\n'
    for post in sorted_posts:
        post_links_html += f'      <li class="post-card"><a href="{post["filename"]}">{post["title"]}</a></li>\n'
    post_links_html += "    </ul>"

    index_content = template_html.replace('{{ARTICLE_TITLE}}', "Product Spotlight - Home")
    index_content = index_content.replace('{{ARTICLE_CONTENT}}', post_links_html)
    
    cache_buster = str(int(time.time()))
    index_content = index_content.replace('{{CACHE_BUSTER}}', cache_buster)

    deploy_to_disk('index.html', index_content, web_app_path)

def delete_from_disk(filename, web_app_path):
    """
    Deletes a specific file from the local disk.
    """
    try:
        full_path = os.path.join(web_app_path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            logging.info(f"Successfully deleted '{filename}' from disk.")
        else:
            logging.info(f"File '{filename}' not found on disk, no action needed.")
        return True
    except OSError as e:
        logging.error(f"An OS error occurred while trying to delete '{filename}': {e}")
        return False

def list_html_files_on_disk(web_app_path):
    """
    Lists all .html files in the web app directory.
    """
    try:
        if not os.path.isdir(web_app_path):
            logging.warning(f"Web app path '{web_app_path}' does not exist. Returning empty list.")
            return []
            
        files = os.listdir(web_app_path)
        html_files = [f for f in files if f.endswith('.html')]
        logging.info(f"Found {len(html_files)} HTML files on disk.")
        return html_files
    except OSError as e:
        logging.error(f"An OS error occurred while trying to list files: {e}")
        return None 