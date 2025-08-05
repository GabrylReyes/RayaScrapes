import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import StringIO


def send_email(results_df):
    """Send the scraped job results via email."""
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO", sender_email)
    email_password = os.environ.get("EMAIL_PASS")

    if not sender_email or not email_password:
        print("❌ Email credentials not set. Skipping email sending.")
        return

    # Convert DataFrame to CSV text
    csv_buffer = StringIO()
    results_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"Job Scraper Results — {len(results_df)} Jobs Found"
    msg.attach(MIMEText(f"Here are the latest job scraper results:\n\n{csv_data}", "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, email_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def scrape_jobs():
    """Scrape job listings from the Akraya job board for multiple locations."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.binary_location = "/usr/bin/chromium-browser"

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    locations_to_search = ["San Diego, CA", "Mountain View, CA"]
    location_results = {}

    def safe_find(job, selector, attr=None):
        """Safely find element text or attribute from a job card."""
        try:
            el = job.find_element(By.CSS_SELECTOR, selector)
            if attr:
                return el.get_attribute(attr)
            return el.text.strip()
        except:
            return None

    try:
        for location in locations_to_search:
            driver.get("https://jobs.akraya.com/index.smpl")

            # Wait until location search box is ready
            wait.until(EC.presence_of_element_located((By.ID, "location-quicksearch")))

            # Search location
            search_box = driver.find_element(By.ID, "location-quicksearch")
            search_box.clear()
            search_box.send_keys(location)
            search_box.send_keys(Keys.RETURN)

            # Wait for job results to load
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".clearfix.hmg-jb-row")))

            # Grab ALL rows
            all_rows = driver.find_elements(By.CSS_SELECTOR, ".clearfix.hmg-jb-row")

            results = []
            for row in all_rows:
                title = safe_find(row, "h3.job-post-title a")  # More reliable than POST_TITLE span
                if not title:
                    continue  # skip rows that aren't job listings

                job_location = safe_find(row, ".job-post-location.POST_LOCATION")
                link = safe_find(row, "h3.job-post-title a", attr="href")
                date_posted = safe_find(row, ".job-post-date .POST_DATE_F")

                results.append({
                    "Title": title,
                    "Location": job_location,
                    "Date Posted": date_posted if date_posted else None,
                    "Link": link
                })

            print(f"Found {len(results)} jobs in {location}.\n")

            df = pd.DataFrame(results)

            if not df.empty:
                df['Date Posted'] = pd.to_datetime(df['Date Posted'], format="%m/%d/%y", errors='coerce')
                df = df.sort_values(by=['Date Posted'], ascending=False)
                df['Date Posted'] = df['Date Posted'].fillna("Unknown")

            location_results[location] = df

    finally:
        driver.quit()

    return location_results


if __name__ == "__main__":
    job_data = scrape_jobs()

    for location, df in job_data.items():
        print(f"\nJobs in {location}:\n")
        if not df.empty:
            print(df.to_string(index=False))
            send_email(df)
        else:
            print("No jobs found.")
