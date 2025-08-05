import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys # Import Keys for pressing Enter
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time # Import time for explicit sleep

def scrape_jobs():
    # Configure Chrome options for headless browsing
    options = Options()
    options.add_argument("--headless=new") # Use the new headless mode
    options.add_argument("--window-size=1920,1080")
    # Add a realistic User-Agent to mimic a normal browser
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    # Initialize the Chrome WebDriver
    driver = webdriver.Chrome(options=options)

    # Define the locations to search for
    locations_to_search = ["San Diego, CA", "Mountain View, CA"]
    
    # Initialize HTML string for results
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

    # Helper function to safely find elements and extract text/attributes
    def safe_find(parent_element, selector, attr=None):
        try:
            el = parent_element.find_element(By.CSS_SELECTOR, selector)
            return el.get_attribute(attr) if attr else el.text.strip()
        except:
            return None

    try:
        # Step 1: Navigate to the base URL
        base_url = "https://jobs.akraya.com/"
        print(f"Navigating to: {base_url}")
        driver.get(base_url)

        # Initialize WebDriverWait for explicit waits
        wait = WebDriverWait(driver, 20) # Increased wait time for robustness

        for location in locations_to_search:
            print(f"Searching for jobs in {location}...")

            try:
                # Step 2: Locate the "location-quicksearch" search box
                # Wait until the search input field is present and clickable
                location_search_box = wait.until(
                    EC.element_to_be_clickable((By.ID, "location-quicksearch"))
                )
                
                # Clear any pre-existing text in the search box
                location_search_box.clear()
                
                # Step 3: Enter the location into the search box
                location_search_box.send_keys(location)
                
                # Step 4: Press Enter
                location_search_box.send_keys(Keys.ENTER)
                
                # Step 5: Press Enter again to actually start the search (as per your observation)
                # Sometimes a second Enter is needed to trigger the form submission after auto-suggestions
                time.sleep(1) # Small delay before second enter if needed
                location_search_box.send_keys(Keys.ENTER)

                # Step 6: Give it time to load (5-10 seconds)
                # Wait for job results or a "no results" message to appear
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".job-post-row, .no-results"))
                )
                # Add a small explicit sleep after the wait to ensure content is fully rendered
                time.sleep(2) 

            except Exception as e:
                print(f"CRITICAL: Timeout or error during search for {location}. Saving debug files. Error: {e}")
                # Sanitize location for filename
                location_filename = location.replace(' ', '_').replace(',', '')
                driver.save_screenshot(f"debug_screenshot_{location_filename}.png")
                with open(f"debug_page_source_{location_filename}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                
                # After a failed search, navigate back to the base URL to reset for the next location
                print("Navigating back to base URL to reset for the next search...")
                driver.get(base_url)
                wait.until(EC.presence_of_element_located((By.ID, "location-quicksearch"))) # Wait for search box to be ready again
                continue # Skip to the next location

            # Find all job posting elements
            jobs = driver.find_elements(By.CSS_SELECTOR, ".job-post-row")
            print(f"Found {len(jobs)} jobs in {location}.")

            results = []
            if jobs:
                for job in jobs:
                    # Extract job title, location, date posted, and link
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

            # Create a Pandas DataFrame from the results
            df = pd.DataFrame(results)
            all_results_html += f"<h2>Jobs in {location}</h2>"

            if not df.empty:
                # Convert 'Date Posted' to datetime objects, handling errors
                df['Date Posted'] = pd.to_datetime(df['Date Posted'], format="%m/%d/%y", errors='coerce')
                # Sort by date posted in descending order
                df = df.sort_values(by=['Date Posted'], ascending=False)
                # Format date back to string and handle NaT (Not a Time) values
                df['Date Posted'] = df['Date Posted'].dt.strftime('%Y-%m-%d').fillna("N/A")
                # Make the link clickable in the HTML output
                df['Link'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Apply</a>' if x else 'N/A')
                
                # Append the DataFrame as an HTML table to the results string
                all_results_html += df.to_html(index=False, escape=False, justify='left')
            else:
                all_results_html += "<p>No jobs found for this location.</p>"
            
            # After processing a location, navigate back to the base URL for the next search
            if location != locations_to_search[-1]:
                print("Navigating back to base URL for next search...")
                driver.get(base_url)
                wait.until(EC.presence_of_element_located((By.ID, "location-quicksearch"))) # Wait for search box to be ready again

    finally:
        # Ensure the browser is closed even if an error occurs
        driver.quit()
    
    # Close the main HTML tags
    all_results_html += "</body></html>"
    
    # Save the aggregated HTML results to a file
    with open("akraya_jobs.html", "w", encoding="utf-8") as f:
        f.write(all_results_html)
    print("Scraping complete. Results saved to akraya_jobs.html")

if __name__ == "__main__":
    scrape_jobs()
