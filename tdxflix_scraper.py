#!/usr/bin/env python3
"""
TDXFlix Complete Scraper - Fetches player URLs for ALL videos
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from datetime import datetime
from collections import Counter
import re
import base64

class TDXFlixScraper:
    def __init__(self, base_url="https://tdxflix.art/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://tdxflix.art/'
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
    
    def extract_player_url(self, video_page_url):
        """Extract iframe player URL from video page"""
        try:
            html = self.fetch_page(video_page_url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for iframe in the page
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                player_url = iframe['src']
                
                # Handle relative URLs
                if player_url.startswith('/'):
                    player_url = urljoin(self.base_url, player_url)
                
                return player_url
            
            return None
            
        except Exception as e:
            print(f"✗ Error extracting player URL from {video_page_url}: {e}")
            return None
    
    def extract_video_source_from_player(self, player_url):
        """Extract actual video source from player page"""
        try:
            if not player_url:
                return None
            
            print(f"  Fetching player: {player_url[:50]}...")
            html = self.fetch_page(player_url)
            if not html:
                return None
            
            # Check if it's the encoded player URL format
            if 'player-x.php' in player_url:
                # Extract the q parameter
                parsed = urlparse(player_url)
                query_params = parse_qs(parsed.query)
                
                if 'q' in query_params:
                    encoded_data = query_params['q'][0]
                    try:
                        # URL decode then base64 decode
                        url_decoded = unquote(encoded_data)
                        # Add padding if needed
                        decoded_bytes = base64.b64decode(url_decoded + '=' * (4 - len(url_decoded) % 4))
                        decoded_str = decoded_bytes.decode('utf-8')
                        
                        # Extract video source from decoded string
                        src_match = re.search(r'src=(["\'])(.*?)\1', decoded_str)
                        if src_match:
                            return src_match.group(2)
                    except Exception as e:
                        print(f"    Decoding error: {e}")
            
            # Parse HTML response for video source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for video tag
            video = soup.find('video')
            if video:
                if video.get('src'):
                    return video['src']
                source = video.find('source')
                if source and source.get('src'):
                    return source['src']
            
            # Look for source tags anywhere
            source = soup.find('source')
            if source and source.get('src'):
                return source['src']
            
            # Look for script tags containing video config
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    url_pattern = r'(https?://[^\s"\']+\.(?:mp4|m3u8|webm|ogg)[^\s"\']*)'
                    urls = re.findall(url_pattern, script.string)
                    if urls:
                        return urls[0]
            
            return None
            
        except Exception as e:
            print(f"✗ Error extracting video source: {e}")
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
                time.sleep(0.5)
            
            time.sleep(2)
        
        return self.all_videos
    
    def scrape_video_page(self, video_url):
        """Scrape individual video page for more details including player"""
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
            
            # Extract player URL
            player_url = self.extract_player_url(video_url)
            if player_url:
                details['player_url'] = player_url
                
                # Try to extract actual video source from player
                video_source = self.extract_video_source_from_player(player_url)
                if video_source:
                    details['video_source'] = video_source
            
        except Exception as e:
            print(f"Error scraping video page: {e}")
        
        return details
    
    def enhance_all_videos(self, start_from=0, delay=2):
        """
        Enhance ALL videos with player URLs and video sources
        Args:
            start_from: Index to start from (useful for resuming)
            delay: Delay between requests in seconds
        """
        total = len(self.all_videos)
        print(f"\n🔍 Enhancing ALL {total} videos with page details...")
        print(f"   This will take approximately {total * delay / 60:.1f} minutes")
        
        successful = 0
        failed = 0
        
        for i, video in enumerate(self.all_videos[start_from:], start=start_from):
            if video.get('url'):
                print(f"\n  [{i+1}/{total}] Processing: {video.get('title', '')[:50]}...")
                
                try:
                    details = self.scrape_video_page(video['url'])
                    if details:
                        video.update(details)
                        if details.get('player_url'):
                            successful += 1
                            print(f"    ✅ Player URL found")
                        if details.get('video_source'):
                            print(f"    ✅ Video source found")
                    else:
                        failed += 1
                        print(f"    ❌ No details retrieved")
                    
                except Exception as e:
                    failed += 1
                    print(f"    ❌ Error: {e}")
                
                # Progress indicator
                if (i + 1) % 10 == 0:
                    print(f"\n📊 Progress: {i+1}/{total} | Successful: {successful} | Failed: {failed}")
                
                # Be respectful to the server
                time.sleep(delay)
        
        print(f"\n✅ Enhancement complete!")
        print(f"   Total processed: {total}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        
        return successful, failed
    
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
            'videos_with_player': sum(1 for v in self.all_videos if v.get('player_url')),
            'videos_with_source': sum(1 for v in self.all_videos if v.get('video_source')),
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
                'version': '2.0'
            },
            'seo_analysis': self.generate_seo_analysis(),
            'videos': self.all_videos
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Data saved to {self.output_file}")
        print(f"   Total videos: {len(self.all_videos)}")
        print(f"   Videos with player URLs: {sum(1 for v in self.all_videos if v.get('player_url'))}")
        print(f"   Videos with source URLs: {sum(1 for v in self.all_videos if v.get('video_source'))}")
        print(f"   File size: {os.path.getsize(self.output_file)} bytes")
        
        return final_data
    
    def print_summary(self):
        """Print summary of scraped data"""
        print("\n" + "="*60)
        print("📊 SCRAPE SUMMARY")
        print("="*60)
        print(f"Total Videos: {len(self.all_videos)}")
        print(f"Videos with Player URLs: {sum(1 for v in self.all_videos if v.get('player_url'))}")
        print(f"Videos with Source URLs: {sum(1 for v in self.all_videos if v.get('video_source'))}")
        print(f"Success Rate: {sum(1 for v in self.all_videos if v.get('player_url'))/len(self.all_videos)*100:.1f}%")
        
        if self.all_videos:
            print(f"\n📌 First video sample:")
            print(f"  Title: {self.all_videos[0].get('title', 'N/A')[:50]}")
            if self.all_videos[0].get('player_url'):
                print(f"  Player: {self.all_videos[0].get('player_url', 'N/A')[:50]}...")
            if self.all_videos[0].get('video_source'):
                print(f"  Source: {self.all_videos[0].get('video_source', 'N/A')[:50]}...")
        
        print("="*60)

def main():
    print("🚀 TDXFlix Scraper Starting...")
    print("="*60)
    
    # Initialize scraper
    scraper = TDXFlixScraper()
    
    # Step 1: Scrape main pages
    print("\n📥 STEP 1: Scraping video list...")
    videos = scraper.scrape_main_page(max_pages=3)
    
    if not videos:
        print("❌ No videos scraped")
        return
    
    print(f"\n✅ Found {len(videos)} videos total")
    
    # Step 2: Ask user if they want to fetch all player URLs
    print("\n" + "="*60)
    print("🎥 STEP 2: Fetch player URLs and video sources")
    print("="*60)
    print(f"Total videos to process: {len(videos)}")
    print(f"Estimated time: ~{len(videos) * 2 / 60:.1f} minutes")
    print("\nOptions:")
    print("1. Process ALL videos (full scrape)")
    print("2. Process only first 10 videos (quick test)")
    print("3. Resume from a specific index")
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    if choice == "1":
        # Process ALL videos
        successful, failed = scraper.enhance_all_videos(start_from=0, delay=2)
        
    elif choice == "2":
        # Quick test - first 10 videos
        print("\n🔍 Quick test: Processing first 10 videos...")
        for i, video in enumerate(scraper.all_videos[:10]):
            if video.get('url'):
                print(f"\n  [{i+1}/10] Processing: {video.get('title', '')[:30]}...")
                details = scraper.scrape_video_page(video['url'])
                if details:
                    video.update(details)
                time.sleep(2)
                
    elif choice == "3":
        # Resume from index
        try:
            start_idx = int(input("Enter starting index (0-based): "))
            successful, failed = scraper.enhance_all_videos(start_from=start_idx, delay=2)
        except ValueError:
            print("❌ Invalid index, processing all videos")
            successful, failed = scraper.enhance_all_videos(start_from=0, delay=2)
    else:
        print("❌ Invalid choice, processing all videos")
        successful, failed = scraper.enhance_all_videos(start_from=0, delay=2)
    
    # Step 3: Print summary and save
    scraper.print_summary()
    scraper.save_to_json()
    
    print("\n✨ Scraping completed successfully!")

if __name__ == "__mai
