import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys # <-- Make sure this is imported
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_jobs():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)

    locations_to_search = ["San Diego, CA", "Mountain View, CA"]
    all_results_html = "<html><head><style>body{font-family: sans-serif;} table{border-collapse: collapse; width: 100%;} th, td{border: 1px solid #dddddd; text-align: left; padding: 8px;} tr:nth-child(even){background-color: #f2f2f2;} th{background-color: #4CAF50; color: white;}</style></head><body>"
    all_results_html += "<h1>Akraya Job Postings</h1>"

    def safe_find(job, selector, attr=None):
        try:
            el = job.find_element(By.CSS_SELECTOR, selector)
            return el.get_attribute(attr) if attr else el.text.strip()
        except:
            return None

    try:
        for location in locations_to_search:
            print(f"Searching for jobs in {location}...")
            driver.get("https://jobs.akraya.com/index.smpl")

            wait = WebDriverWait(driver, 15)
            search_box = wait.until(
                EC.presence_of_element_located((By.ID, "location-quicksearch"))
            )
            search_box.clear()
            search_box.send_keys(location)
            
            # === THE FIX IS HERE ===
            # The site searches when you press Enter, no button click is needed.
            search_box.send_keys(Keys.RETURN)

            # Wait for the results to load by checking for the job rows
            # We add a small clause to handle the "No matching jobs found" case
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".job-post-row, .no-results"))
                )
            except Exception:
                print(f"Timeout waiting for results in {location}. The page might not have updated correctly.")
                continue

            jobs = driver.find_elements(By.CSS_SELECTOR, ".job-post-row")
            print(f"Found {len(jobs)} jobs in {location}.")

            results = []
            if jobs:
                for job in jobs:
                    title = safe_find(job, "h3.job-post-title a")
                    job_location = safe_find(job, ".job-post-location")
                    date_posted = safe_find(job, ".job-post-date")
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
                all_results_html += "<p>No jobs found.</p>"

    finally:
        driver.quit()
    
    all_results_html += "</body></html>"
    
    with open("akraya_jobs.html", "w") as f:
        f.write(all_results_html)
    print("Scraping complete. Results saved to akraya_jobs.html")


if __name__ == "__main__":
    scrape_jobs()
