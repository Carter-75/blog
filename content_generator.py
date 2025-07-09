import logging
import requests
import json
import re
from utils import extract_title_from_html

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_content(product_info, provider_config):
    """
    Generates a blog post about a specific product using a content generation AI.

    Args:
        product_info (dict): A dictionary containing the product's 'title' and 'description'.
        provider_config (dict): A dictionary with the settings for the content provider.

    Returns:
        str: The generated blog post content, or None if an error occurs.
    """
    provider = provider_config.get('provider')
    if provider == 'ollama':
        return _generate_with_ollama(product_info, provider_config.get('ollama_settings', {}))
    # Add other providers here if needed
    else:
        logging.error(f"Unsupported content provider: {provider}")
        return None

def _generate_with_ollama(product_info, settings):
    """Generates content using a local Ollama model."""
    url = settings.get('base_url', 'http://localhost:11434/api/generate')
    model = settings.get('model', 'llama3:8b')
    
    product_title = product_info.get('title', 'the selected product')
    product_desc = product_info.get('description', '')

    # --- Initial Draft Prompt ---
    prompt_template = """You are an expert SEO writer. Your task is to write a blog post based on the provided product info.

**Product Name:** {product_title}
**Product Description:** {product_desc}

---INSTRUCTIONS---
1.  **Write an engaging, SEO-optimized blog post** about the product.
2.  **Structure:** The post must have a main title (`<h2>`), subheadings (`<h3>`), and paragraphs (`<p>`).
3.  **Output Format:** Your response MUST be ONLY the raw HTML content. Do NOT include a call to action link, `<html>`, `<body>`, markdown like ````html````, or any commentary.

---PERFECT OUTPUT EXAMPLE---
<h2>This is a Perfect Title</h2>
<h3>This is a Subheading</h3>
<p>This is a paragraph about the product, explaining its many benefits and why the reader should be excited.</p>
<p>This is another paragraph, continuing the persuasive narrative.</p>
---END OF EXAMPLE---

Now, generate the HTML for the product: {product_title}.
"""
    prompt = prompt_template.format(product_title=product_title, product_desc=product_desc)

    logging.info(f"Generating initial draft for product '{product_title}' using Ollama model '{model}'...")
    initial_draft_html = _call_ollama(url, model, prompt)

    if not initial_draft_html:
        logging.error("Failed to generate an initial draft.")
        return None
    
    logging.info("Initial draft generated. Proceeding to a single review-and-correct pass.")

    # --- Single Self-Correction Step ---
    # We now only do ONE review pass. The loop was inefficient and caused instability.
    final_article_html = _review_and_correct_with_ollama(initial_draft_html, product_title, settings)
    
    if not final_article_html:
        logging.warning("Self-correction phase failed. Using the initial draft as a fallback.")
        final_article_html = initial_draft_html

    # --- Templating Logic ---
    try:
        with open('template.html', 'r', encoding='utf-8') as f:
            template_html = f.read()
    except FileNotFoundError:
        logging.error("Could not find template.html. Cannot proceed with templating.")
        return None # Return None as we cannot construct the final page
    
    # Extract the title from the *final* content
    article_title = extract_title_from_html(final_article_html) or product_title
    
    # Replace placeholders
    final_html = template_html.replace('{{ARTICLE_TITLE}}', article_title)
    final_html = final_html.replace('{{ARTICLE_CONTENT}}', final_article_html)

    logging.info("Successfully generated, reviewed, and templated content from Ollama.")
    return final_html


def _review_and_correct_with_ollama(draft_html, product_title, settings):
    """
    Takes a draft of HTML, and asks the AI to review, correct, and improve it.
    """
    url = settings.get('base_url', 'http://localhost:11434/api/generate')
    model = settings.get('model', 'llama3:8b')

    review_prompt_template = """You are a meticulous editor. Your task is to correct the following HTML blog post draft.

---DRAFT HTML---
{draft_html}
---END OF DRAFT---

---INSTRUCTIONS---
1.  **Review the Draft:** Fix any grammar, spelling, or flow issues. Make the content more persuasive and engaging.
2.  **Output Format:** Your response MUST be ONLY the raw, corrected HTML content. Do NOT add a call-to-action link, `<html>`, `<body>`, markdown like ````html````, or any commentary like 'Here is the corrected version...'.

---PERFECT OUTPUT EXAMPLE---
<h2>This is a Corrected Title</h2>
<h3>This is a Corrected Subheading</h3>
<p>This is a corrected paragraph. It is now more engaging and error-free.</p>
<p>This is another corrected paragraph.</p>
---END OF EXAMPLE---

Now, provide ONLY the corrected HTML.
"""
    review_prompt = review_prompt_template.format(draft_html=draft_html)

    logging.info(f"Sending draft for '{product_title}' for self-correction...")
    corrected_content = _call_ollama(url, model, review_prompt)

    return corrected_content


def _call_ollama(url, model, prompt):
    """
    A helper function to make a single request to the Ollama API and handle responses.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7 # A bit of creativity is fine
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        response_data = response.json()
        
        article_content = response_data.get('response', '').strip()

        if not article_content:
            logging.error("Received an empty response from Ollama.")
            return None
        
        # More robust cleanup to handle commentary and markdown wrappers.
        # It finds the HTML within ```html ... ```, even with text before/after.
        match = re.search(r'```html(.*?)```', article_content, re.DOTALL)
        if match:
            article_content = match.group(1).strip()
        
        # As a final measure, find the first real HTML tag to strip any leading text
        # that survived (like 'Here is the code:')
        first_tag_pos = article_content.find('<')
        if first_tag_pos > 0:
            article_content = article_content[first_tag_pos:]
        
        return article_content.strip()

    except requests.exceptions.Timeout:
        logging.error(f"The request to Ollama timed out. The model might be too slow or unresponsive.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred while communicating with Ollama: {e}")
        return None
    except json.JSONDecodeError:
        logging.error("Failed to decode the JSON response from Ollama. Response was not valid JSON.")
        logging.error(f"Raw response: {response.text}")
        return None


if __name__ == '__main__':
    # Add the helper function here for testing
    # Example usage for testing
    with open('config.json', 'r') as f:
        config = json.load(f)

    # A mock product_info object for testing purposes
    mock_product_info = {
        "title": "The Ultimate Keto Diet Plan",
        "description": "A comprehensive guide to losing weight and improving your health with the ketogenic diet. Includes meal plans, recipes, and expert tips."
    }

    content = generate_content(mock_product_info, config.get('content_provider'))
    
    if content:
        print("\n--- Generated Content ---\n")
        print(content)
        # Save to a test file to check formatting
        with open("test_generated_content.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("\nContent saved to test_generated_content.html")
    else:
        print("Failed to generate content.") 