import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def scrape_jobs():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)

    locations_to_search = ["San Diego, CA", "Mountain View, CA"]
    
    all_results_html = """
    <html>
    <head>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            h1 { color: #333; }
            h2 { color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px; }
            table { border-collapse: collapse; width: 100%; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
            th, td { border: 1px solid #dddddd; text-align: left; padding: 12px; }
            th { background-color: #4CAF50; color: white; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
            p { color: #777; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>Akraya Job Postings</h1>
    """

    def safe_find(parent_element, selector, attr=None):
        try:
            el = parent_element.find_element(By.CSS_SELECTOR, selector)
            return el.get_attribute(attr) if attr else el.text.strip()
        except:
            return None

    try:
        base_url = "https://jobs.akraya.com/"
        
        for location in locations_to_search:
            print(f"Searching for jobs in {location}...")
            
            # Navigate to the base URL for each search to ensure a clean state
            print(f"Navigating to: {base_url}")
            driver.get(base_url)

            wait = WebDriverWait(driver, 20)

            try:
                # Wait until the search box element is present in the DOM
                location_search_box = wait.until(
                    EC.presence_of_element_located((By.ID, "location-quicksearch"))
                )

                # Then, wait until the element is clickable (visible and not disabled)
                location_search_box = wait.until(
                    EC.element_to_be_clickable((By.ID, "location-quicksearch"))
                )

                location_search_box.clear()
                location_search_box.send_keys(location)
                location_search_box.send_keys(Keys.ENTER)
                time.sleep(1) # Small delay for auto-suggestions to appear if any
                location_search_box.send_keys(Keys.ENTER)

                # Wait for the job results or "no results" message
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".job-post-row, .no-results"))
                )
                time.sleep(2) # Added a final sleep to ensure all content is rendered

            except Exception as e:
                print(f"CRITICAL: Timeout or error during search for {location}. Saving debug files. Error: {e}")
                location_filename = location.replace(' ', '_').replace(',', '')
                driver.save_screenshot(f"debug_screenshot_{location_filename}.png")
                with open(f"debug_page_source_{location_filename}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                continue

            jobs = driver.find_elements(By.CSS_SELECTOR, ".job-post-row")
            print(f"Found {len(jobs)} jobs in {location}.")

            results = []
            if jobs:
                for job in jobs:
                    title = safe_find(job, "h3.job-post-title a .POST_TITLE")
                    job_location = safe_find(job, ".job-post-location .POST_LOCATION")
                    date_posted = safe_find(job, ".job-post-date .POST_DATE_F")
                    link = safe_find(job, "h3.job-post-title a", attr="href")

                    results.append({
                        "Title": title,
                        "Location": job_location,
                        "Date Posted": date_posted,
                        "Link": link
                    })

            df = pd.DataFrame(results)
            all_results_html += f"<h2>Jobs in {location}</h2>"

            if not df.empty:
                df['Date Posted'] = pd.to_datetime(df['Date Posted'], format="%m/%d/%y", errors='coerce')
                df = df.sort_values(by=['Date Posted'], ascending=False)
                df['Date Posted'] = df['Date Posted'].dt.strftime('%Y-%m-%d').fillna("N/A")
                df['Link'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Apply</a>' if x else 'N/A')
                all_results_html += df.to_html(index=False, escape=False, justify='left')
            else:
                all_results_html += "<p>No jobs found for this location.</p>"

    finally:
        driver.quit()
    
    all_results_html += "</body></html>"
    
    with open("akraya_jobs.html", "w", encoding="utf-8") as f:
        f.write(all_results_html)
    print("Scraping complete. Results saved to akraya_jobs.html")

if __name__ == "__main__":
    scrape_jobs()
