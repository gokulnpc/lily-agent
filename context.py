import csv
import time
import random
import os
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import tempfile

def setup_driver():
    """Set up a Chrome WebDriver with appropriate options."""
    print("Setting up Chrome WebDriver...")
    
    # Create a unique temporary directory for Chrome data
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")
    
    chrome_options = Options()
    
    # Add options to make the browser more stable
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    chrome_options.add_argument("--disable-site-isolation-trials")
    
    # Set window size
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Add user agent to mimic a real browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # Add experimental options
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Set user data directory
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    
    try:
        # Use webdriver_manager to handle driver installation
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(20)
        
        print("Chrome WebDriver setup successful")
        return driver
    except Exception as e:
        print(f"Error setting up Chrome WebDriver: {e}")
        return None

def safe_navigate(driver, url, max_retries=3):
    """Safely navigate to a URL with retry mechanism."""
    for attempt in range(max_retries):
        try:
            print(f"Navigating to {url} (attempt {attempt+1}/{max_retries})")
            driver.get(url)
            
            # Wait for the page to load
            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Check if we got an access denied page
            if "Access Denied" in driver.title or "Forbidden" in driver.title:
                print("Access denied page detected, retrying...")
                if attempt < max_retries - 1:
                    delay = random.uniform(5, 10)
                    print(f"Waiting {delay:.1f} seconds before retry...")
                    time.sleep(delay)
                    continue
                else:
                    print("Max retries reached for access denied page")
                    return False
            
            # Wait a bit longer for dynamic content to load
            time.sleep(3)
            
            # Scroll down to load more content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Add a small random delay to appear more human-like
            time.sleep(random.uniform(1, 3))
            return True
            
        except Exception as e:
            print(f"Error navigating to {url}: {e}")
            if attempt < max_retries - 1:
                delay = random.uniform(2, 5)
                print(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                print(f"Failed to navigate to {url} after {max_retries} attempts")
                return False

def extract_blog_data(driver, base_url):
    """Extract blog titles and URLs from the page."""
    blogs = []
    
    try:
        # Wait for the blog container to be present
        print("Waiting for blog container...")
        wait = WebDriverWait(driver, 30)
        blog_container = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main'].blog.row"))
        )
        
        # Find all blog links - both hero articles and regular articles
        selectors = [
            "a.blog__hero-article",  # Featured blog
            "a.article-card"         # Regular blog entries
        ]
        
        blog_links = []
        for selector in selectors:
            try:
                print(f"Finding blogs with selector: {selector}")
                links = blog_container.find_elements(By.CSS_SELECTOR, selector)
                print(f"Found {len(links)} links with {selector}")
                blog_links.extend(links)
            except Exception as e:
                print(f"Error with selector {selector}: {e}")
        
        if not blog_links:
            print("No blog links found")
            return blogs
        
        print(f"Found total {len(blog_links)} blog links")
        
        for idx, link in enumerate(blog_links, 1):
            try:
                # Extract the URL
                url = link.get_attribute("href")
                if not url:
                    continue
                
                # Extract title from URL
                url_path = url.split('/blog/')[-1].rstrip('/')
                title = url_path.replace('-', ' ').title()
                
                if not title:
                    continue
                
                blogs.append({
                    'title': title,
                    'url': url
                })
                
            except Exception as e:
                print(f"Error extracting blog data: {e}")
                continue
        
    except Exception as e:
        print(f"Error in extract_blog_data: {e}")
    
    return blogs

def scrape_all_blogs(base_url, num_pages=18):
    """Scrape all blog pages and extract titles and URLs."""
    all_blogs = []
    driver = None
    
    try:
        driver = setup_driver()
        if not driver:
            print("Failed to set up WebDriver")
            return all_blogs
        
        for page_num in range(1, num_pages + 1):
            page_url = f"{base_url}?start={page_num}"
            print(f"\nProcessing page {page_num}/{num_pages}")
            
            if not safe_navigate(driver, page_url):
                print(f"Skipping page {page_num} due to navigation error")
                continue
            
            blogs = extract_blog_data(driver, base_url)
            all_blogs.extend(blogs)
            
            print(f"Found {len(blogs)} blogs on page {page_num}")
            print(f"Total blogs collected so far: {len(all_blogs)}")
            
            # Add a delay between pages to avoid being blocked
            if page_num < num_pages:
                delay = random.uniform(2, 4)
                print(f"Waiting {delay:.1f} seconds before next page...")
                time.sleep(delay)
    
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    return all_blogs

def save_to_csv(blogs, filename):
    """Save the scraped blog data to a CSV file."""
    if not blogs:
        print("No blog data to save")
        return
    
    try:
        fieldnames = ['title', 'url']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(blogs)
        
        print(f"\nSuccessfully saved {len(blogs)} blogs to {filename}")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")

if __name__ == "__main__":
    base_url = "https://www.partselect.com/content/blog"
    output_file = "partselect_blogs.csv"
    
    print(f"Starting to scrape blogs from {base_url}")
    blogs = scrape_all_blogs(base_url)
    
    if blogs:
        print(f"\nTotal blogs collected: {len(blogs)}")
        save_to_csv(blogs, output_file)
    else:
        print("No blogs were collected") 
        
        import requests
from bs4 import BeautifulSoup
import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, WebDriverException
import urllib.parse
import socket
import random

def setup_driver():
    """Set up and return a configured Chrome driver."""
    try:
        print("Setting up Chrome options...")
        chrome_options = Options()
        
        # Set a realistic user agent
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        chrome_options.add_argument(f'user-agent={user_agent}')
        
        # Add headers to appear more like a real browser
        chrome_options.add_argument('--accept-language=en-US,en;q=0.9')
        chrome_options.add_argument('--accept=text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        
        # Basic options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        
        # Add unique user data directory
        import tempfile
        import os
        temp_dir = os.path.join(tempfile.gettempdir(), f"chrome_temp_{os.getpid()}")
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")
        print(f"Using temporary directory: {temp_dir}")
        
        # Additional stability options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-notifications")
        
        # Disable automation flags
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Page load strategy
        chrome_options.page_load_strategy = 'normal'
        
        print("Chrome options configured. Attempting to create driver...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Execute CDP commands to disable automation
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        print("Chrome driver created successfully")
        
        # Set timeouts
        print("Setting timeouts...")
        driver.set_page_load_timeout(60)  # Increased timeout
        driver.set_script_timeout(30)
        driver.implicitly_wait(20)  # Increased implicit wait
        
        return driver
    except Exception as e:
        print(f"Failed to create driver: {str(e)}")
        raise

def safe_get_text(element):
    """Safely get text from an element."""
    try:
        return element.text.strip()
    except:
        return ""

def safe_get_attribute(element, attribute):
    """Safely get attribute from an element."""
    try:
        return element.get_attribute(attribute)
    except:
        return ""

def wait_for_element(driver, by, value, timeout=10):
    """Wait for an element to be present."""
    try:
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.presence_of_element_located((by, value)))
        return element
    except:
        return None

def extract_percentage(text):
    """Extract percentage from text."""
    try:
        return text.split("%")[0].strip()
    except:
        return "0"

def get_symptom_data(symptom_element):
    """Extract data from a symptom element."""
    try:
        print("Extracting symptom data...")
        
        # Get the URL first as it's most likely to succeed
        print("Getting URL...")
        url = safe_get_attribute(symptom_element, "href")
        print(f"Found URL: {url}")
        
        # Get the symptom name
        print("Getting symptom name...")
        try:
            title = symptom_element.find_element(By.CLASS_NAME, "title-md")
            symptom = safe_get_text(title)
            print(f"Found symptom: {symptom}")
        except Exception as e:
            print(f"Error getting symptom name: {e}")
            return None
        
        # Get the description
        print("Getting description...")
        try:
            description = safe_get_text(symptom_element.find_element(By.TAG_NAME, "p"))
            print(f"Found description: {description[:50]}...")  # Print first 50 chars
        except Exception as e:
            print(f"Error getting description: {e}")
            return None
        
        # Get the percentage
        print("Getting percentage...")
        try:
            percentage_element = symptom_element.find_element(By.CLASS_NAME, "symptom-list__reported-by")
            percentage = extract_percentage(safe_get_text(percentage_element))
            print(f"Found percentage: {percentage}")
        except Exception as e:
            print(f"Error getting percentage: {e}")
            return None
        
        return {
            'symptom': symptom,
            'description': description,
            'percentage': percentage,
            'symptom_detail_url': url
        }
    except Exception as e:
        print(f"Error extracting symptom data: {e}")
        return None

def get_repair_details(driver, url):
    """Get repair details from a symptom page."""
    try:
        driver.get(url)
        wait_for_element(driver, By.CLASS_NAME, "repair__intro")
        
        # Get difficulty
        difficulty = ""
        difficulty_item = driver.find_element(By.CSS_SELECTOR, "ul.list-disc li")
        if difficulty_item:
            difficulty = safe_get_text(difficulty_item)
            difficulty = difficulty.replace("Rated as", "").strip()
        
        # Get parts
        parts = []
        part_links = driver.find_elements(By.CSS_SELECTOR, "div.repair__intro a.js-scrollTrigger")
        for link in part_links:
            part_name = safe_get_text(link)
            if part_name:
                parts.append(part_name)
        
        # Get video URL
        video_url = ""
        try:
            video_element = driver.find_element(By.CSS_SELECTOR, "div[data-yt-init]")
            if video_element:
                video_id = safe_get_attribute(video_element, "data-yt-init")
                if video_id:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    print(f"Found video URL: {video_url}")
        except Exception as e:
            print(f"No video found or error getting video URL: {e}")
        
        return {
            'parts': ", ".join(parts),
            'difficulty': difficulty,
            'repair_video_url': video_url
        }
    except Exception as e:
        print(f"Error getting repair details: {e}")
        return {'parts': '', 'difficulty': '', 'repair_video_url': ''}

def safe_navigate(driver, url, max_retries=3):
    """Safely navigate to a URL with retries and ensure page is fully loaded."""
    for attempt in range(max_retries):
        try:
            print(f"Navigating to {url} (attempt {attempt+1}/{max_retries})")
            
            # Add a random delay between attempts
            if attempt > 0:
                delay = random.uniform(3, 7)
                print(f"Waiting {delay:.1f} seconds before retry...")
                time.sleep(delay)
            
            driver.get(url)
            
            # Wait for document ready state to be complete
            wait = WebDriverWait(driver, 30)
            wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            print("Page load complete")
            
            # Check for access denied
            if "Access Denied" in driver.title:
                print("Access Denied page detected")
                if attempt < max_retries - 1:
                    print("Retrying with delay...")
                    continue
                return False
            
            # Verify we can find some basic elements
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                print("Found body element")
                return True
            except TimeoutException:
                print("Timeout waiting for body element")
                if attempt < max_retries - 1:
                    print("Retrying...")
                    continue
                
        except Exception as e:
            print(f"Navigation error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("Retrying after error...")
            else:
                print(f"Failed to navigate to {url} after {max_retries} attempts")
                return False
    
    return False

def scrape_repairs(base_url, appliance_type):
    """
    Scrape repair information from the website.
    
    Args:
        base_url: The URL to scrape from
        appliance_type: The type of appliance (e.g., 'Dishwasher', 'Refrigerator')
    """
    repairs_data = []
    driver = None
    
    try:
        driver = setup_driver()
        print(f"\nProcessing {appliance_type} repairs...")
        print(f"Attempting to navigate to {base_url}")
        
        # Use safe navigation
        if not safe_navigate(driver, base_url):
            print(f"Failed to load the {appliance_type} base URL")
            return repairs_data
            
        print("Waiting for symptom list...")
        # Wait longer for the symptom list
        wait = WebDriverWait(driver, 30)  # Increased timeout
        try:
            symptom_list = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "symptom-list")))
            print("Found symptom list")
        except TimeoutException:
            print("Timeout waiting for symptom list")
            # Try to print the page source for debugging
            try:
                print("\nPage source:")
                print(driver.page_source[:500])  # Print first 500 chars
            except:
                print("Could not get page source")
            return repairs_data
        
        # Get all symptom elements and store their data immediately
        print("Collecting all symptom elements...")
        symptom_elements = symptom_list.find_elements(By.TAG_NAME, "a")
        print(f"Found {len(symptom_elements)} symptoms")
        
        # Store the initial data to prevent stale elements
        symptom_data_list = []
        for idx, element in enumerate(symptom_elements, 1):
            try:
                print(f"\nCollecting initial data for symptom {idx}/{len(symptom_elements)}")
                # Store the URL and href immediately
                url = safe_get_attribute(element, "href")
                if not url:
                    print("No URL found for symptom, skipping")
                    continue
                    
                # Try to get the HTML content of the element
                html_content = element.get_attribute('outerHTML')
                print(f"Element HTML: {html_content[:200]}...")  # Print first 200 chars
                
                symptom_data = get_symptom_data(element)
                if symptom_data:
                    symptom_data_list.append(symptom_data)
                    print(f"Successfully collected initial data for symptom: {symptom_data['symptom']}")
                else:
                    print("Failed to collect symptom data")
                
            except Exception as e:
                print(f"Error collecting initial symptom data: {e}")
                continue
        
        # Now process each collected symptom data
        print(f"\nProcessing {len(symptom_data_list)} collected symptoms")
        for idx, symptom_data in enumerate(symptom_data_list, 1):
            try:
                print(f"\nProcessing symptom {idx}/{len(symptom_data_list)}: {symptom_data['symptom']}")
                
                # Get repair details using the stored URL
                full_url = urllib.parse.urljoin(base_url, symptom_data['symptom_detail_url'])
                print(f"Getting repair details from: {full_url}")
                repair_details = get_repair_details(driver, full_url)
                
                # Combine all data
                repair_entry = {
                    'Product': appliance_type,
                    'symptom': symptom_data['symptom'],
                    'description': symptom_data['description'],
                    'percentage': symptom_data['percentage'],
                    'parts': repair_details['parts'],
                    'symptom_detail_url': full_url,
                    'difficulty': repair_details['difficulty'],
                    'repair_video_url': repair_details['repair_video_url']
                }
                
                repairs_data.append(repair_entry)
                print(f"Successfully processed: {repair_entry['symptom']}")
                print(f"Parts found: {repair_entry['parts']}")
                print(f"Difficulty: {repair_entry['difficulty']}")
                if repair_entry['repair_video_url']:
                    print(f"Video URL: {repair_entry['repair_video_url']}")
                
            except Exception as e:
                print(f"Error processing symptom: {e}")
                continue
            
            # Add a small delay between symptoms
            delay = random.uniform(2, 4)
            print(f"Waiting {delay:.1f} seconds before next symptom...")
            time.sleep(delay)
    
    except Exception as e:
        print(f"Error during scraping: {e}")
        # Try to print the page source for debugging
        try:
            if driver:
                print("\nPage source:")
                print(driver.page_source[:500])  # Print first 500 chars
        except:
            pass
    
    finally:
        if driver:
            driver.quit()
    
    return repairs_data

def process_appliance(appliance_type, base_url, output_file):
    """Process repairs for a specific appliance type."""
    print(f"\nStarting {appliance_type} repair information scraping...")
    repairs_data = scrape_repairs(base_url, appliance_type)
    
    if repairs_data:
        print(f"\nFound {len(repairs_data)} repair entries for {appliance_type}")
        save_to_csv(repairs_data, output_file)
        return len(repairs_data)
    else:
        print(f"No repair data was collected for {appliance_type}")
        return 0

def save_to_csv(data, filename):
    """Save the scraped data to a CSV file."""
    if not data:
        print("No data to save")
        return
    
    try:
        fieldnames = ['Product', 'symptom', 'description', 'percentage', 'parts', 'symptom_detail_url', 'difficulty', 'repair_video_url']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        print(f"\nSuccessfully saved {len(data)} repairs to {filename}")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")

if __name__ == "__main__":
    appliances = [
        {
            'type': 'Dishwasher',
            'url': 'https://www.partselect.com/Repair/Dishwasher/',
            'output': 'dishwasher_repairs.csv'
        },
        {
            'type': 'Refrigerator',
            'url': 'https://www.partselect.com/Repair/Refrigerator/',
            'output': 'refrigerator_repairs.csv'
        }
    ]
    
    total_repairs = 0
    for appliance in appliances:
        repairs_count = process_appliance(
            appliance['type'],
            appliance['url'],
            appliance['output']
        )
        total_repairs += repairs_count
        
        # Add a longer delay between appliances
        if appliance != appliances[-1]:  # If not the last appliance
            delay = random.uniform(5, 10)
            print(f"\nWaiting {delay:.1f} seconds before processing next appliance...")
            time.sleep(delay)
    
    print(f"\nScraping completed. Total repairs found across all appliances: {total_repairs}") 
    
    import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, WebDriverException
import urllib.parse
import socket
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed


def wait_and_find_element(driver, by, value, timeout=10):
    """Helper function to wait for an element and handle stale element exceptions"""
    wait = WebDriverWait(driver, timeout)
    try:
        element = wait.until(EC.presence_of_element_located((by, value)))
        return element
    except (TimeoutException, StaleElementReferenceException):
        return None


def wait_and_find_elements(driver, by, value, timeout=10):
    """Helper function to wait for elements and handle stale element exceptions"""
    wait = WebDriverWait(driver, timeout)
    try:
        elements = wait.until(EC.presence_of_all_elements_located((by, value)))
        return elements
    except (TimeoutException, StaleElementReferenceException):
        return []


def safe_get_text(element):
    """Safely get text from an element, handling stale element exceptions"""
    try:
        return element.text
    except StaleElementReferenceException:
        return "N/A"


def safe_get_attribute(element, attribute):
    """Safely get attribute from an element, handling stale element exceptions"""
    try:
        return element.get_attribute(attribute)
    except StaleElementReferenceException:
        return "N/A"
    

def is_valid_url(url):
    """Check if a URL is valid and can be resolved"""
    try:
        # Parse the URL
        parsed_url = urllib.parse.urlparse(url)
        # Check if the URL has a scheme and netloc
        if not parsed_url.scheme or not parsed_url.netloc:
            return False
        
        # Try to resolve the domain
        socket.gethostbyname(parsed_url.netloc)
        return True
    except (ValueError, socket.gaierror):
        return False


def safe_navigate(driver, url, max_retries=3):
    """Safely navigate to a URL with retries and ensure page is fully loaded"""
    for attempt in range(max_retries):
        try:
            #print(f"Navigating to {url} (attempt {attempt+1}/{max_retries})")
            driver.get(url)
            
            # Wait for document ready state to be complete
            wait = WebDriverWait(driver, 30)
            wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            
            # Determine if this is a product page or category page based on URL
            is_product_page = "/PS" in url or ".htm" not in url
            
            # Wait for key elements that indicate the page has loaded
            try:
                if is_product_page:
                    # For product pages, wait for product-specific elements
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pd__wrap")))
                    # Also wait for price container which is crucial
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.price.pd__price")))
                else:
                    # For category pages, wait for navigation and product list
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.container")))
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "nf__links")))
                
                #print(f"Page loaded successfully: {url}")
                return True
            except TimeoutException as e:
                print(f"Timeout waiting for key elements to load: {str(e)}")
                # Check if the page actually loaded despite timeout
                try:
                    if is_product_page:
                        # Try alternative elements for product pages
                        if driver.find_elements(By.CSS_SELECTOR, "div.pd__wrap") or \
                           driver.find_elements(By.CSS_SELECTOR, "span.price"):
                            print("Page appears to be loaded despite timeout")
                            return True
                    else:
                        # Try alternative elements for category pages
                        if driver.find_elements(By.CSS_SELECTOR, "div.nf__part"):
                            print("Page appears to be loaded despite timeout")
                            return True
                except:
                    pass
                
                if attempt < max_retries - 1:
                    print("Retrying...")
                    time.sleep(5)
                continue
                
        except WebDriverException as e:
            print(f"Navigation error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("Retrying after error...")
                time.sleep(5)
            else:
                print(f"Failed to navigate to {url} after {max_retries} attempts")
                return False
    
    return False


def extract_text_after_header(element, header_text):
    """Extract text after a header in an element"""
    try:
        full_text = safe_get_text(element)
        if header_text in full_text:
            return full_text.replace(header_text, "").strip()
        return full_text
    except Exception:
        return "N/A"


def scrape_part_info(driver, part_name, product_url):
    """
    Scrape information for a specific part from its product page.
    
    Args:
        driver: Selenium WebDriver instance
        part_name: Name of the part
        product_url: URL of the product page
        
    Returns:
        dict: Dictionary containing the part information
    """
    data = {
        'part_name': part_name,
        'part_id': 'N/A',
        'mpn_id': 'N/A',
        'part_price': 'N/A',
        'install_difficulty': 'N/A',
        'install_time': 'N/A',
        'symptoms': 'N/A',
        'product_types': 'N/A',
        'replace_parts': 'N/A',
        'brand': 'N/A',
        'availability': 'N/A',
        'install_video_url': 'N/A',
        'product_url': product_url
    }
    
    # Navigate to the product page
    if not safe_navigate(driver, product_url):
        print(f"Failed to navigate to product {part_name}. Skipping.")
        return data
    
    # Find product ID
    product_id_elements = wait_and_find_elements(driver, By.CSS_SELECTOR, "span[itemprop='productID']")
    if product_id_elements:
        data['part_id'] = safe_get_text(product_id_elements[0])
    
    # Find brand information
    brand_element = wait_and_find_element(driver, By.CSS_SELECTOR, "span[itemprop='brand'] span[itemprop='name']")
    if brand_element:
        data['brand'] = safe_get_text(brand_element)
    
    # Find availability information
    availability_element = wait_and_find_element(driver, By.CSS_SELECTOR, "span[itemprop='availability']")
    if availability_element:
        data['availability'] = safe_get_text(availability_element)
    
    # Find installation video URL
    video_container = wait_and_find_element(driver, By.CSS_SELECTOR, "div.yt-video")
    if video_container:
        video_id = safe_get_attribute(video_container, "data-yt-init")
        if video_id:
            data['install_video_url'] = f"https://www.youtube.com/watch?v={video_id}"
    
    # Find MPN ID
    mpn_elements = wait_and_find_elements(driver, By.CSS_SELECTOR, "span[itemprop='mpn']")
    if mpn_elements:
        data['mpn_id'] = safe_get_text(mpn_elements[0])
    
    # Find replace parts
    replace_parts_elements = wait_and_find_elements(driver, By.CSS_SELECTOR, "div[data-collapse-container='{\"targetClassToggle\":\"d-none\"}']")
    if replace_parts_elements:
        data['replace_parts'] = safe_get_text(replace_parts_elements[0])
    
    # Find part price
    wait = WebDriverWait(driver, 10)
    price_container = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "span.price.pd__price"))
    )
    
    if price_container:
        # Wait a short time for any dynamic price updates
        time.sleep(1)
        
        # Try multiple approaches to get the price
        price_found = False
        
        # Approach 1: Direct js-partPrice
        price_element = price_container.find_element(By.CSS_SELECTOR, "span.js-partPrice")
        if price_element:
            price_text = safe_get_text(price_element)
            if price_text and price_text != "N/A":
                data['part_price'] = price_text
                price_found = True
        
        # Approach 2: Get from content attribute if direct text failed
        if not price_found:
            price_content = safe_get_attribute(price_container, "content")
            if price_content and price_content != "N/A":
                data['part_price'] = price_content
                price_found = True
        
        # Approach 3: Try getting complete text including currency symbol
        if not price_found:
            full_price = safe_get_text(price_container)
            if full_price and full_price != "N/A":
                data['part_price'] = full_price
                price_found = True
        
        if not price_found:
            print("Warning: Price element found but could not extract price text")
    
    # Find troubleshooting information
    pd_wrap = wait_and_find_element(driver, By.CSS_SELECTOR, "div.pd__wrap.row")
    if pd_wrap:
        # Find all col-md-6 mt-3 divs within the pd_wrap
        info_divs = pd_wrap.find_elements(By.CSS_SELECTOR, "div.col-md-6.mt-3")
        
        for div in info_divs:
            # Get the header text
            header = div.find_element(By.CSS_SELECTOR, "div.bold.mb-1")
            if not header:
                continue
                
            header_text = safe_get_text(header)
            
            # Check which type of information this div contains
            if "This part fixes the following symptoms:" in header_text:
                # Extract symptoms
                data['symptoms'] = extract_text_after_header(div, header_text)
            elif "This part works with the following products:" in header_text:
                # Extract product types
                data['product_types'] = extract_text_after_header(div, header_text)
    
    # Find install difficulty and time
    install_container = wait_and_find_element(driver, By.CSS_SELECTOR, "div.d-flex.flex-lg-grow-1.col-lg-7.col-12.justify-content-lg-between.mt-lg-0.mt-2")
    
    if install_container:
        # Find the two d-flex divs inside the container
        d_flex_divs = install_container.find_elements(By.CLASS_NAME, "d-flex")
        
        if len(d_flex_divs) >= 2:
            # First div contains difficulty
            difficulty_p = d_flex_divs[0].find_element(By.TAG_NAME, "p")
            if difficulty_p:
                data['install_difficulty'] = safe_get_text(difficulty_p)
            
            # Second div contains time
            time_p = d_flex_divs[1].find_element(By.TAG_NAME, "p")
            if time_p:
                data['install_time'] = safe_get_text(time_p)
    
    # Print all extracted data
    # print(f"Part ID: {data['part_id']}")
    # print(f"MPN ID: {data['mpn_id']}")
    # print(f"Part Price: {data['part_price']}")
    # print(f"Install Difficulty: {data['install_difficulty']}")
    # print(f"Install Time: {data['install_time']}")
    # print(f"Symptoms: {data['symptoms']}")
    # print(f"Product Types: {data['product_types']}")
    # print(f"Replace Parts: {data['replace_parts']}")
    # print(f"Brand: {data['brand']}")
    # print(f"Availability: {data['availability']}")
    # print(f"Install Video URL: {data['install_video_url']}")
    
    return data


def process_category_page(driver, link_url):
    """
    Process a category page and scrape all parts within it.
    
    Args:
        driver: Selenium WebDriver instance
        link_url: URL of the category page
        
    Returns:
        list: List of dictionaries containing part information
    """
    parts_data = []
    print(f"\nVisiting: {link_url}")
    
    # Navigate to the category page
    if not safe_navigate(driver, link_url):
        print(f"Failed to navigate to {link_url}. Skipping.")
        return parts_data
    
    # Find all divs with class name "nf__part mb-3" using CSS selector
    part_divs = wait_and_find_elements(driver, By.CSS_SELECTOR, "div.nf__part.mb-3")
    if not part_divs:
        print(f"No parts found in category {link_url}. Skipping.")
        return parts_data
        
    print(f"Found {len(part_divs)} parts")
    
    # Store part information to avoid stale element issues
    part_info = []
    for part_div in part_divs:
        a_tag = part_div.find_element(By.CLASS_NAME, "nf__part__detail__title")
        if not a_tag:
            continue
            
        part_name = safe_get_text(a_tag.find_element(By.TAG_NAME, "span"))
        href = safe_get_attribute(a_tag, "href")
        
        # Validate the URL
        if href and is_valid_url(href):
            part_info.append((part_name, href))
        else:
            print(f"Skipping invalid product URL: {href}")
    
    if not part_info:
        print(f"No valid parts found in category {link_url}. Skipping.")
        return parts_data
    
    # Process each part in the category
    parts_data = process_parts_in_category(driver, part_info, link_url)
    
    return parts_data

def process_parts_in_category(driver, part_info, category_url):
    """
    Process all parts in a category.
    
    Args:
        driver: Selenium WebDriver instance
        part_info: List of tuples containing (part_name, product_url)
        category_url: URL of the category page to return to
        
    Returns:
        list: List of dictionaries containing part information
    """
    parts_data = []
    for part_name, product_url in part_info:
        print(f"\nProcessing part: {part_name}")
        
        # Scrape part information
        part_data = scrape_part_info(driver, part_name, product_url)
        parts_data.append(part_data)
        
        # Go back to the category page
        if not safe_navigate(driver, category_url):
            print(f"Failed to return to category page. Skipping remaining parts.")
            return parts_data
    
    return parts_data

def setup_driver():
    """
    Set up and return a configured Chrome driver.
    
    Returns:
        webdriver.Chrome: Configured Chrome driver
    """
    try:
        print("Setting up Chrome options...")
        chrome_options = Options()
        
        # Start with minimal options for testing
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Add page load strategy
        chrome_options.page_load_strategy = 'normal'
        
        print("Initializing Chrome driver...")
        driver = webdriver.Chrome(options=chrome_options)
        print("Chrome driver initialized successfully")
        
        # Set longer page load timeout
        print("Setting page load timeout...")
        driver.set_page_load_timeout(60)  # Increased timeout to 60 seconds
        
        # Set script timeout
        driver.set_script_timeout(30)
        
        return driver
    except Exception as e:
        print(f"Failed to create driver: {str(e)}")
        print("Please ensure Chrome is installed and chromedriver is in your PATH")
        raise

def process_brand_with_retry(brand_url, max_retries=3):
    """
    Process a brand page and its related pages with retry mechanism.
    
    Args:
        brand_url: URL of the brand page to process
        max_retries: Maximum number of retry attempts
        
    Returns:
        list: List of dictionaries containing part information
    """
    brand_parts_data = []
    driver = None
    
    for attempt in range(max_retries):
        try:
            # Set up driver for this brand
            driver = setup_driver()
            
            # Step 1: Navigate to brand page
            if not safe_navigate(driver, brand_url):
                print(f"Failed to navigate to brand page {brand_url}. Retrying...")
                if driver:
                    driver.quit()
                continue
            
            # Step 2: Process all products from the brand page
            print("Processing products from brand page...")
            brand_data = process_category_page(driver, brand_url)
            brand_parts_data.extend(brand_data)
            print(f"Found {len(brand_data)} products on brand page")
            
            # Step 3: Collect all Related part pages
            print("Collecting related part pages...")
            related_links = get_related_links(driver)
            print(f"Found {len(related_links)} related part pages")
            
            # Step 4: Process each related page sequentially
            for rel_idx, related_url in enumerate(related_links, 1):
                print(f"\nProcessing related page {rel_idx}/{len(related_links)}: {related_url}")
                if not safe_navigate(driver, related_url):
                    print(f"Failed to navigate to related page {related_url}. Skipping.")
                    continue
                
                related_data = process_category_page(driver, related_url)
                brand_parts_data.extend(related_data)
                print(f"Found {len(related_data)} products on related page")
                
                # Add a small delay between processing related pages
                time.sleep(1)
            
            # Successfully processed brand and its related pages
            print(f"Successfully processed brand {brand_url}")
            driver.quit()
            return brand_parts_data
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for brand {brand_url}: {e}")
            if driver:
                driver.quit()
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(5)
            else:
                print(f"Failed to process brand {brand_url} after {max_retries} attempts")
                return brand_parts_data
    
    return brand_parts_data

def get_brand_links(driver, base_url):
    """Get all brand links from the main page"""
    brand_links = []
    if not safe_navigate(driver, base_url):
        print("Failed to navigate to main page")
        return brand_links

    # Wait for the main navigation links
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "nf__links")))
        ul_tags = driver.find_elements(By.CLASS_NAME, "nf__links")
        if ul_tags:
            # First ul contains brand links
            li_tags = ul_tags[0].find_elements(By.TAG_NAME, "li")
            print(f"Found {len(li_tags)} brand links")
            
            for li_tag in li_tags:
                try:
                    a_tag = li_tag.find_element(By.TAG_NAME, "a")
                    link_url = safe_get_attribute(a_tag, "href")
                    if link_url and is_valid_url(link_url):
                        brand_links.append(link_url)
                        print(f"Found brand link: {link_url}")
                except Exception as e:
                    print(f"Error processing brand link: {e}")
                    continue
    except Exception as e:
        print(f"Error finding brand links: {e}")
    
    return brand_links

def get_related_links(driver):
    """Get all related part page links from the current page"""
    related_links = []
    try:
        # Find section titles
        section_titles = driver.find_elements(By.CLASS_NAME, "section-title")
        for title in section_titles:
            try:
                title_text = safe_get_text(title)
                if "Related" in title_text and ("Dishwasher Parts" in title_text or "Refrigerator Parts" in title_text):
                    print(f"Found related section: {title_text}")
                    # Find the next ul.nf__links after this title
                    related_ul = title.find_element(By.XPATH, "./following::ul[@class='nf__links'][1]")
                    if related_ul:
                        li_tags = related_ul.find_elements(By.TAG_NAME, "li")
                        print(f"Found {len(li_tags)} related category links")
                        
                        for li_tag in li_tags:
                            try:
                                a_tag = li_tag.find_element(By.TAG_NAME, "a")
                                link_url = safe_get_attribute(a_tag, "href")
                                if link_url and is_valid_url(link_url):
                                    related_links.append(link_url)
                                    print(f"Found related link: {link_url}")
                            except Exception as e:
                                print(f"Error processing related link: {e}")
                                continue
            except Exception as e:
                print(f"Error processing section title: {e}")
                continue
    except Exception as e:
        print(f"Error finding related links: {e}")
    
    return related_links

def scrape_all_parts(base_url):
    """
    Scrape all parts following the correct processing logic with parallel brand processing:
    1. Gather links from all brands at the main page
    2. Process brands in parallel, for each brand:
        a. Process all products from the brand page
        b. Collect all Related part pages
        c. Process all products from each related page sequentially
    
    Args:
        base_url: The base URL to start scraping from
        
    Returns:
        list: List of dictionaries containing part information
    """
    all_parts_data = []
    driver = None
    
    try:
        # Set up initial driver
        print("\nSetting up browser...")
        driver = setup_driver()
        
        # Step 1: Gather all brand links from main page
        print("\nStep 1: Gathering brand links from main page...")
        brand_links = get_brand_links(driver, base_url)
        
        # Clean up initial driver as we'll create new ones for parallel processing
        driver.quit()
        driver = None
        
        if not brand_links:
            print("No brand links found. Exiting.")
            return all_parts_data
        
        # Process brands in parallel
        max_workers = max(1, min(5, len(brand_links)))  # Limit to max 3 workers
        print(f"\nProcessing {len(brand_links)} brands with {max_workers} parallel workers")
        
        completed_brands = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all brand processing tasks
            future_to_url = {
                executor.submit(process_brand_with_retry, url): url 
                for url in brand_links
            }
            
            # Process completed brand tasks
            for future in as_completed(future_to_url):
                brand_url = future_to_url[future]
                try:
                    brand_data = future.result()
                    all_parts_data.extend(brand_data)
                    completed_brands += 1
                    print(f"\nCompleted brand {completed_brands}/{len(brand_links)}: {brand_url}")
                    print(f"Found {len(brand_data)} total products for this brand")
                    print(f"Progress: {completed_brands}/{len(brand_links)} brands processed")
                except Exception as e:
                    print(f"Error processing brand {brand_url}: {e}")
    
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    print(f"\nScraping completed. Total parts found: {len(all_parts_data)}")
    return all_parts_data

def save_to_csv(parts_data, filename):
    """
    Save the parts data to a CSV file.
    
    Args:
        parts_data: List of dictionaries containing part information
        filename: Name of the CSV file to save to
    """
    if not parts_data:
        print("No data to save.")
        return
    
    try:
        # Get the fieldnames from the first dictionary
        fieldnames = parts_data[0].keys()
        
        # Write to CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parts_data)
        
        print(f"Successfully saved {len(parts_data)} parts to {filename}")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")

if __name__ == "__main__":
    # # Base URL for PartSelect dishwasher parts
    # base_url = "https://www.partselect.com/Dishwasher-Parts.htm"
    
    # # Scrape all parts
    # print("Starting dishwasher parts scraping...")
    # parts_data = scrape_all_parts(base_url)
    # print(f"Found {len(parts_data)} dishwasher parts")
    
    # # Save to CSV
    # save_to_csv(parts_data, "dishwasher_parts.csv")
    
    # Scrape refrigerator parts
    base_url = "https://www.partselect.com/Refrigerator-Parts.htm"
    print("\nStarting refrigerator parts scraping...")
    parts_data = scrape_all_parts(base_url)
    print(f"Found {len(parts_data)} refrigerator parts")
    
    # Save to CSV
    save_to_csv(parts_data, "refrigerator_parts.csv")
    