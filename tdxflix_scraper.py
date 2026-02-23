#!/usr/bin/env python3
"""
TDXFlix Complete Scraper - Single File Version
Scrapes videos, images, metadata, and saves to tdxflix.json
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime
from collections import Counter
import re

class TDXFlixScraper:
    def __init__(self, base_url="https://tdxflix.art/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.all_videos = []
        self.output_file = "tdxflix.json"
        
    def fetch_page(self, url):
        """Fetch page content with error handling"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            print(f"✓ Fetched: {url}")
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching {url}: {e}")
            return None
    
    def parse_video_article(self, article):
        """Parse individual video article element"""
        video_data = {}
        
        try:
            # Get video link
            link = article.find('a')
            if link and link.get('href'):
                video_data['url'] = urljoin(self.base_url, link['href'])
                video_data['title'] = link.get('title', '').strip()
            
            # Get thumbnail image
            img = article.find('img', class_='video-main-thumb')
            if img:
                video_data['thumbnail'] = img.get('src') or img.get('data-lazy-src', '')
                video_data['alt_text'] = img.get('alt', '').strip()
            
            # Get data attributes
            video_data['video_id'] = article.get('data-video-id', '')
            video_data['post_id'] = article.get('data-post-id', '')
            video_data['main_thumb'] = article.get('data-main-thumb', '')
            
            # Get tags from class
            classes = article.get('class', [])
            video_data['tags'] = [c for c in classes if c not in [
                'loop-video', 'thumb-block', 'video-preview-item', 'full-width', 
                'post', 'type-post', 'status-publish', 'format-standard', 'hentry'
            ]]
            
            # Get duration
            duration = article.find('span', class_='duration')
            if duration:
                video_data['duration'] = duration.text.strip()
            
            # Get HD tag
            hd_tag = article.find('span', class_='hd-video')
            video_data['hd'] = bool(hd_tag)
            
            # Get header title
            header = article.find('header', class_='entry-header')
            if header:
                span = header.find('span')
                if span:
                    video_data['display_title'] = span.text.strip()
            
            video_data['scraped_at'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"✗ Error parsing article: {e}")
        
        return video_data
    
    def scrape_main_page(self, max_pages=5):
        """Scrape main page and pagination"""
        page_url = self.base_url
        
        for page_num in range(1, max_pages + 1):
            print(f"\n📄 Scraping page {page_num}...")
            
            if page_num > 1:
                page_url = f"{self.base_url}page/{page_num}/"
            
            html = self.fetch_page(page_url)
            if not html:
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all video articles
            articles = soup.find_all('article', class_=lambda x: x and 'loop-video' in x)
            
            if not articles:
                print("No more videos found")
                break
            
            print(f"Found {len(articles)} videos on page {page_num}")
            
            for article in articles:
                video_data = self.parse_video_article(article)
                if video_data and video_data.get('url'):
                    self.all_videos.append(video_data)
                time.sleep(0.5)  # Be respectful to server
            
            time.sleep(2)  # Delay between pages
        
        return self.all_videos
    
    def scrape_video_page(self, video_url):
        """Scrape individual video page for more details"""
        html = self.fetch_page(video_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        details = {}
        
        try:
            # Get video title
            title = soup.find('h1', class_='entry-title')
            if title:
                details['full_title'] = title.text.strip()
            
            # Get video description
            description = soup.find('div', class_='entry-content')
            if description:
                details['description'] = description.text.strip()[:500]
            
            # Get meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                if meta.get('name') == 'keywords':
                    details['meta_keywords'] = meta.get('content', '')
                elif meta.get('name') == 'description':
                    details['meta_description'] = meta.get('content', '')
            
        except Exception as e:
            print(f"Error scraping video page: {e}")
        
        return details
    
    def enhance_with_video_details(self, max_videos=10):
        """Enhance first N videos with individual page data"""
        print(f"\n🔍 Enhancing {min(max_videos, len(self.all_videos))} videos with page details...")
        
        for i, video in enumerate(self.all_videos[:max_videos]):
            if video.get('url'):
                print(f"  Processing video {i+1}/{max_videos}")
                details = self.scrape_video_page(video['url'])
                if details:
                    video.update(details)
                time.sleep(1)
    
    def generate_seo_analysis(self):
        """Generate SEO analysis and add to JSON"""
        if not self.all_videos:
            return {}
        
        # Extract all tags
        all_tags = []
        for video in self.all_videos:
            if video.get('tags'):
                all_tags.extend(video['tags'])
        
        tag_counter = Counter(all_tags)
        
        # Extract keywords from titles
        all_title_words = []
        for video in self.all_videos:
            if video.get('title'):
                words = re.findall(r'\w+', video['title'].lower())
                all_title_words.extend(words)
            if video.get('display_title'):
                words = re.findall(r'\w+', video['display_title'].lower())
                all_title_words.extend(words)
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'video', 'sex', 'nude', 'hot'}
        keywords = [w for w in all_title_words if w not in stop_words and len(w) > 2]
        keyword_counter = Counter(keywords)
        
        seo_analysis = {
            'total_videos': len(self.all_videos),
            'videos_with_titles': sum(1 for v in self.all_videos if v.get('title')),
            'videos_with_alt': sum(1 for v in self.all_videos if v.get('alt_text')),
            'videos_with_duration': sum(1 for v in self.all_videos if v.get('duration')),
            'videos_with_tags': sum(1 for v in self.all_videos if v.get('tags')),
            'videos_with_hd': sum(1 for v in self.all_videos if v.get('hd')),
            'top_tags': dict(tag_counter.most_common(20)),
            'top_keywords': dict(keyword_counter.most_common(30)),
            'scrape_date': datetime.now().isoformat(),
            'total_tags_found': len(all_tags),
        }
        
        return seo_analysis
    
    def save_to_json(self):
        """Save all data to tdxflix.json"""
        final_data = {
            'metadata': {
                'site': self.base_url,
                'total_videos': len(self.all_videos),
                'scraped_at': datetime.now().isoformat(),
                'version': '1.0'
            },
            'seo_analysis': self.generate_seo_analysis(),
            'videos': self.all_videos
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Data saved to {self.output_file}")
        print(f"   Total videos: {len(self.all_videos)}")
        print(f"   File size: {os.path.getsize(self.output_file)} bytes")
        
        return final_data
    
    def print_summary(self):
        """Print summary of scraped data"""
        print("\n" + "="*50)
        print("📊 SCRAPE SUMMARY")
        print("="*50)
        print(f"Total Videos: {len(self.all_videos)}")
        
        if self.all_videos:
            print(f"First video: {self.all_videos[0].get('title', 'N/A')[:50]}")
            print(f"Sample tags: {self.all_videos[0].get('tags', [])[:5]}")
            
            # Count unique tags
            all_tags = []
            for v in self.all_videos:
                all_tags.extend(v.get('tags', []))
            print(f"Unique tags: {len(set(all_tags))}")
        
        print("="*50)

def main():
    print("🚀 TDXFlix Scraper Starting...")
    print("="*50)
    
    # Initialize scraper
    scraper = TDXFlixScraper()
    
    # Scrape main pages
    videos = scraper.scrape_main_page(max_pages=3)  # Adjust pages as needed
    
    if videos:
        # Enhance with video page details (optional)
        scraper.enhance_with_video_details(max_videos=5)
        
        # Print summary
        scraper.print_summary()
        
        # Save to tdxflix.json
        scraper.save_to_json()
        
        print("\n✨ Scraping completed successfully!")
    else:
        print("❌ No videos scraped")

if __name__ == "__main__":
    main()
