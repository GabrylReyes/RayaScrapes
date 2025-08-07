# scraper.py
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode


def send_email(results_df):
    """Send the scraped job results via email as an HTML table."""
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO", sender_email)
    email_password = os.environ.get("EMAIL_PASS")

    if not sender_email or not email_password:
        print("❌ Email credentials not set in environment variables. Skipping email.")
        return

    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            th {{ background-color: #4CAF50; color: white; }}
        </style>
    </head>
    <body>
        <h2>Akraya Job Alert 🤖</h2>
        <p>Found <strong>{len(results_df)}</strong> new jobs posted in the last 30 days (excluding remote):</p>
        {results_df.to_html(index=False)}
        <p>This is an automated message from your Python scraper.</p>
    </body>
    </html>
    """
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"Akraya Job Alert — {len(results_df)} Recent On-Site Jobs Found"
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, email_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def scrape_jobs(location):
    """Scrape job listings from Akraya for a specific location."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    
    results = []

    print(f"\n--- Scraping jobs for: {location} ---")

    try:
        params = {
            'arg': 'jb_search_results',
            'jb_search_submitted': '1',
            'location': location
        }
        base_url = "https://jobs.akraya.com/index.smpl"
        target_url = f"{base_url}?{urlencode(params)}"
        
        print(f"Navigating to: {target_url}")
        driver.get(target_url)

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "JBSearchList_container")))
        print("✅ Results page loaded.")

        # --- FINAL FIX: Add a pause to allow all dynamic content to render ---
        # This prevents a race condition where the newest jobs might be missed.
        print("Pausing for 3 seconds to ensure all jobs are loaded...")
        time.sleep(3)

        print("📜 Scrolling to load all job listings...")
        last_count = 0
        scroll_attempts = 0
        while scroll_attempts < 5: 
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            current_count = len(driver.find_elements(By.CSS_SELECTOR, ".clearfix.hmg-jb-row"))
            
            if current_count == 0 and last_count == 0:
                print("No job listings found on the results page for this location.")
                break

            print(f"Found {current_count} jobs so far...")
            if current_count == last_count:
                print("✅ Finished scrolling.")
                break
            
            last_count = current_count
            scroll_attempts += 1

        jobs = driver.find_elements(By.CSS_SELECTOR, ".clearfix.hmg-jb-row")
        print(f"Parsing {len(jobs)} rows...")

        for job in jobs:
            title_elements = job.find_elements(By.CSS_SELECTOR, "h3.job-post-title")
            if not title_elements:
                continue

            try:
                title = title_elements[0].text.strip()
                job_location = job.find_element(By.CSS_SELECTOR, ".job-post-location.POST_LOCATION").text.strip()
                date_posted = job.find_element(By.CSS_SELECTOR, ".job-post-date .POST_DATE_F").text.strip()
                
                results.append({
                    "Title": title,
                    "Location": job_location,
                    "Date Posted": date_posted
                })
            except Exception:
                continue
    
    except TimeoutException:
        print(f"❌ Timed out waiting for page content for {location}. Skipping.")

    finally:
        driver.quit()

    return pd.DataFrame(results)


if __name__ == "__main__":
    target_locations = ["San Diego, CA", "Mountain View, CA"]
    all_results_dfs = []
    
    print("🚀 Starting multi-location scraper...")
    
    for loc in target_locations:
        df = scrape_jobs(loc)
        if not df.empty:
            all_results_dfs.append(df)
            
    print("\n--- All scraping finished. ---")

    if all_results_dfs:
        final_df = pd.concat(all_results_dfs, ignore_index=True).drop_duplicates()
        print(f"\nScraped a total of {len(final_df)} jobs. Now applying filters...")

        location_pattern = '|'.join([loc.split(',')[0] for loc in target_locations])
        final_df = final_df[final_df['Location'].str.contains(location_pattern, case=False, na=False)].copy()

        final_df['Parsed Date'] = pd.to_datetime(final_df['Date Posted'], format='%m/%d/%y')
        cutoff_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=30)
        recent_jobs_df = final_df[final_df['Parsed Date'] >= cutoff_date].copy()
        
        filtered_df = recent_jobs_df[~recent_jobs_df['Location'].str.contains('remote', case=False, na=False)].copy()

        sorted_df = filtered_df.sort_values(by='Parsed Date', ascending=False)
        
        sorted_df = sorted_df.drop(columns=['Parsed Date'])

        if not sorted_df.empty:
            print(f"\nFound {len(sorted_df)} recent, on-site jobs in target locations.")
            print(sorted_df.to_string())
            send_email(sorted_df)
        else:
            print("\nFound jobs, but none matched all the date and location criteria.")
    else:
        print("\nNo jobs found across all specified locations.")
