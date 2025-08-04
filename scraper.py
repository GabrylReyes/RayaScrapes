# scraper.py
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import StringIO


def send_email(results_df):
    """Send the scraped job results via email."""
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO", sender_email)  # Defaults to sending to yourself
    email_password = os.environ.get("EMAIL_PASS")

    if not sender_email or not email_password:
        print("❌ Email credentials not set. Skipping email sending.")
        return

    # Convert DataFrame to CSV text
    csv_buffer = StringIO()
    results_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    # Create the email
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"Job Scraper Results — {len(results_df)} Jobs Found"

    msg.attach(MIMEText(f"Here are the latest job scraper results:\n\n{csv_data}", "plain"))

    # Send email using Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, email_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def scrape_jobs():
    """Scrape job listings from the Akraya job board."""
    # Setup Chrome options for headless operation in GitHub Actions
    options = Options()
    options.add_argument("--headless=new")  # new headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/chromium-browser"  # Path for GitHub Actions

    driver = webdriver.Chrome(options=options)

    results = []

    try:
        # Search for multiple cities
        cities = ["San Diego, CA", "Mountain View, CA"]

        for city in cities:
            print(f"🔍 Searching for jobs in {city}...")
            driver.get("https://jobs.akraya.com/index.smpl")

            # Find the location input by ID
            search_box = driver.find_element(By.ID, "location-quicksearch")
            search_box.clear()
            search_box.send_keys(city)
            search_box.send_keys(Keys.RETURN)
            search_box.send_keys(Keys.RETURN)  # Some pages require double ENTER

            # Wait for the results page to load
            time.sleep(5)

            # Each job container
            jobs = driver.find_elements(By.CSS_SELECTOR, ".clearfix.hmg-jb-row")
            print(f"Found {len(jobs)} jobs in {city}.\n")

            for job in jobs:
                try:
                    title = job.find_element(By.CSS_SELECTOR, "h3.job-post-title span.POST_TITLE").text.strip()
                    location = job.find_element(By.CSS_SELECTOR, ".job-post-location.POST_LOCATION").text.strip()
                    link = job.find_element(By.CSS_SELECTOR, "h3.job-post-title a").get_attribute("href")
                    date_posted = job.find_element(By.CSS_SELECTOR, ".job-post-date .POST_DATE_F").text.strip()

                    results.append({
                        "Search City": city,
                        "Title": title,
                        "Location": location,
                        "Date Posted": date_posted,
                        "Link": link
                    })
                except Exception as e:
                    print("Error parsing a job listing:", e)

    finally:
        driver.quit()

    return pd.DataFrame(results)
