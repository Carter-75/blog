import logging
from bs4 import BeautifulSoup

def insert_affiliate_links(html_content, product):
    """
    Appends a styled, clickable affiliate link button to the end of the HTML body.
    This function no longer searches for placeholders; it appends directly.

    Args:
        html_content (str): The full HTML content of the blog post.
        product (dict): The product dictionary containing the 'link' and 'title'.

    Returns:
        str: The HTML content with the affiliate link button appended.
    """
    if not product or not product.get('link'):
        logging.warning("No product with a link provided. Cannot insert affiliate button.")
        return html_content

    affiliate_link = product['link']
    product_title = product.get('title', 'this amazing product')
    
    soup = BeautifulSoup(html_content, 'html.parser')

    # Define the call-to-action text and the new button tag
    cta_text = f"Click Here to Learn More About {product_title}!"
    button_html = f'<a href="{affiliate_link}" class="affiliate-button" target="_blank" rel="noopener noreferrer">{cta_text}</a>'
    new_button_tag = BeautifulSoup(button_html, 'html.parser')

    # Find the specific article container to append the button to
    target_container = soup.find('div', class_='article-container')
    
    if not target_container:
        logging.warning("Could not find a `<div class=\"article-container\">` to append the affiliate link. Falling back to `<body>`.")
        target_container = soup.find('body')

    if not target_container:
        logging.warning("Could not find a `<body>` tag either. Appending to the end of the document.")
        # If no body, just append the raw tag to the soup, which is not ideal but a fallback.
        soup.append(new_button_tag)
    else:
        # Wrap the button in a paragraph for proper spacing
        p_tag = soup.new_tag("p")
        p_tag.append(new_button_tag)
        target_container.append(p_tag)
        logging.info(f"Successfully appended affiliate button for: {product_title}")

    return str(soup) 