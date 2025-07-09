import ftplib
import logging
import io
import time

def deploy_to_ftp(filename, content, ftp_config):
    """
    Uploads a file's content to a remote FTP server.

    Args:
        filename (str): The name for the remote file.
        content (str): The content of the file to be uploaded.
        ftp_config (dict): A dictionary containing 'host', 'user', and 'pass'.

    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    try:
        host = ftp_config['host']
        user = ftp_config['user']
        password = ftp_config['pass']
        remote_dir = ftp_config.get('remote_dir', '/htdocs/') # Default for InfinityFree

        logging.info(f"Connecting to FTP host: {host}...")
        with ftplib.FTP(host, user, password, timeout=30) as ftp:
            ftp.cwd(remote_dir)
            
            # Use io.BytesIO to treat the string content like a file
            content_buffer = io.BytesIO(content.encode('utf-8'))
            
            logging.info(f"Uploading {filename} to {remote_dir}...")
            ftp.storbinary(f'STOR {filename}', content_buffer)
            logging.info(f"Successfully uploaded {filename}.")
            
        return True

    except ftplib.all_errors as e:
        logging.error(f"An FTP error occurred: {e}")
        if 'Login incorrect' in str(e):
            logging.error("FTP login credentials in config.json are likely incorrect.")
        return False
    except KeyError as e:
        logging.error(f"Missing FTP configuration key in config.json: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during FTP deployment: {e}")
        return False

def update_index_page(post_history, ftp_config, template_html):
    """
    Generates and uploads an index.html file with a list of all posts.
    It also deletes the default 'index2.html' from the server.
    """
    logging.info("Generating and deploying site index page...")
    
    # Sort posts by timestamp, newest first
    sorted_posts = sorted(
        [p for p in post_history if 'filename' in p],  # Filter out old format records
        key=lambda x: x['timestamp'], 
        reverse=True
    )

    # Generate the list of links with new styling classes
    post_links_html = '<ul class="post-grid">\n'
    for post in sorted_posts:
        post_links_html += f'      <li class="post-card"><a href="{post["filename"]}">{post["title"]}</a></li>\n'
    post_links_html += "    </ul>"

    # Use the main template for the index page, setting a new title
    index_content = template_html.replace('{{ARTICLE_TITLE}}', "Product Spotlight - Home")
    index_content = index_content.replace('{{ARTICLE_CONTENT}}', post_links_html)
    
    # ---=== Cache-Busting ===---
    cache_buster = str(int(time.time()))
    index_content = index_content.replace('{{CACHE_BUSTER}}', cache_buster)

    # Deploy the new index.html
    deploy_to_ftp('index.html', index_content, ftp_config)

    # Clean up the default hosting file
    try:
        host = ftp_config['host']
        user = ftp_config['user']
        password = ftp_config['pass']
        remote_dir = ftp_config.get('remote_dir', '/htdocs/')

        logging.info("Checking for and removing default 'index2.html' file...")
        with ftplib.FTP(host, user, password, timeout=30) as ftp:
            ftp.cwd(remote_dir)
            if 'index2.html' in ftp.nlst():
                ftp.delete('index2.html')
                logging.info("Successfully deleted 'index2.html'.")
            else:
                logging.info("'index2.html' not found, no action needed.")
    except ftplib.all_errors as e:
        logging.warning(f"Could not delete 'index2.html' (this is non-critical): {e}")
    except Exception as e:
        logging.warning(f"An unexpected error occurred while trying to delete 'index2.html': {e}")


def delete_from_ftp(filename, ftp_config):
    """
    Deletes a specific file from the remote FTP server.

    Args:
        filename (str): The name of the file to delete.
        ftp_config (dict): A dictionary containing 'host', 'user', and 'pass'.

    Returns:
        bool: True if deletion was successful or file didn't exist, False on error.
    """
    try:
        host = ftp_config['host']
        user = ftp_config['user']
        password = ftp_config['pass']
        remote_dir = ftp_config.get('remote_dir', '/htdocs/')

        logging.info(f"Connecting to FTP host to delete '{filename}'...")
        with ftplib.FTP(host, user, password, timeout=30) as ftp:
            remote_path = f"{remote_dir.rstrip('/')}/{filename}"
            try:
                ftp.delete(remote_path)
                logging.info(f"Successfully deleted '{filename}' from the server.")
            except ftplib.error_perm as e:
                if '550' in str(e): # 550 means file not found or permission error
                    logging.info(f"File '{filename}' not found on server, no action needed.")
                else:
                    raise # Re-raise other permission errors
        return True
    except ftplib.all_errors as e:
        logging.error(f"An FTP error occurred while trying to delete '{filename}': {e}")
        return False
    except KeyError as e:
        logging.error(f"Missing FTP configuration key for deletion: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during FTP deletion: {e}")
        return False 