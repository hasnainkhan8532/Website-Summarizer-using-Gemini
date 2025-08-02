import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from urllib.parse import urlparse
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please add it to your .env file.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

def is_valid_url(url):
    """Check if the URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def clean_text(text):
    """Clean extracted text by removing extra whitespace and special characters."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?;:()\-]', '', text)
    return text.strip()

def scrape_website(url):
    """Scrape website content and extract meaningful text."""
    try:
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text() if title else "No title found"
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = meta_desc.get('content') if meta_desc else ""
        
        # Extract main content
        # Try to find main content areas
        main_content = ""
        content_selectors = ['main', 'article', '.content', '#content', '.post', '.entry']
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                main_content = content_area.get_text()
                break
        
        # If no main content area found, get all paragraph text
        if not main_content:
            paragraphs = soup.find_all('p')
            main_content = ' '.join([p.get_text() for p in paragraphs])
        
        # Clean and limit content
        main_content = clean_text(main_content)
        
        # Limit content to reasonable size for API (about 3000 characters)
        if len(main_content) > 3000:
            main_content = main_content[:3000] + "..."
        
        return {
            'title': clean_text(title_text),
            'description': clean_text(description),
            'content': main_content,
            'url': url
        }
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching website: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing website: {str(e)}")

def summarize_content(website_data):
    """Use Gemini AI to summarize the website content."""
    try:
        prompt = f"""
        Please provide a comprehensive summary of this website:
        
        Title: {website_data['title']}
        Meta Description: {website_data['description']}
        URL: {website_data['url']}
        
        Content:
        {website_data['content']}
        
        Please provide:
        1. A brief overview of what this website is about
        2. The main purpose or goal of the website
        3. Key topics or services mentioned
        4. Target audience (if apparent)
        
        Keep the summary concise but informative (3-5 paragraphs).
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        raise Exception(f"Error generating summary: {str(e)}")

@app.route('/')
def index():
    """Main page with URL input form."""
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize():
    """Handle URL submission and return summary."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a URL'}), 400
        
        if not is_valid_url(url):
            return jsonify({'error': 'Please provide a valid URL'}), 400
        
        # Scrape website
        website_data = scrape_website(url)
        
        # Generate summary
        summary = summarize_content(website_data)
        
        return jsonify({
            'success': True,
            'title': website_data['title'],
            'url': website_data['url'],
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 