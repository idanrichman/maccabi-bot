"""
Maccabi Appointment Checker Bot

Automatically checks for earlier available appointments on Maccabi4U
and sends Telegram notifications when earlier slots are found.
"""

# =============================================================================
# IMPORTS
# =============================================================================
import json
import logging
import os
import random
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# =============================================================================
# CONSTANTS
# =============================================================================
NOTIFICATIONS_FILE = 'notifications.json'
LOG_FILE = 'maccabi.log'
LOG_MAX_BYTES = 10 * 1_000_000  # 10 MB
LOG_BACKUP_COUNT = 1
CONFIG_FILE = 'config.yaml'

# =============================================================================
# LOGGING SETUP
# =============================================================================
def setup_logger():
    """Configure and return the application logger."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    log_format = '%(asctime)s - %(levelname)-8s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # File handler (DEBUG level)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

    # Stdout handler (INFO level)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(stdout_handler)

    return logger


logger = setup_logger()

# =============================================================================
# CONFIGURATION
# =============================================================================
def load_config():
    """Load configuration from YAML file."""
    with open(CONFIG_FILE, 'r') as stream:
        return yaml.load(stream, yaml.SafeLoader)


config = load_config()

# =============================================================================
# TELEGRAM NOTIFICATIONS
# =============================================================================
def send_telegram_message(message: str, chat_id: str = None, api_key: str = None):
    """Send a message via Telegram Bot API."""
    chat_id = chat_id or config['chat_id']
    api_key = api_key or config['api_key']

    headers = {
        'Content-Type': 'application/json',
        'Proxy-Authorization': 'Basic base64'
    }
    data = json.dumps({
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_notification': True
    })
    url = f'https://api.telegram.org/bot{api_key}/sendMessage'

    response = requests.post(url, data=data, headers=headers, proxies=None, verify=False)
    return response

# =============================================================================
# NOTIFICATION PERSISTENCE
# =============================================================================
def load_notifications():
    """Load sent notifications from file."""
    if os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_notifications(notifications):
    """Save sent notifications to file."""
    with open(NOTIFICATIONS_FILE, 'w') as f:
        json.dump(notifications, f, indent=2)


def was_notified(cur_appoint, first_avail_appoint):
    """Check if we already notified about this first_avail for this cur_appoint."""
    notifications = load_notifications()
    cur_key = cur_appoint.strftime('%Y-%m-%d %H:%M')
    first_key = first_avail_appoint.strftime('%Y-%m-%d %H:%M')
    return notifications.get(cur_key) == first_key


def mark_notified(cur_appoint, first_avail_appoint):
    """Mark that we notified about this first_avail for this cur_appoint."""
    notifications = load_notifications()
    cur_key = cur_appoint.strftime('%Y-%m-%d %H:%M')
    first_key = first_avail_appoint.strftime('%Y-%m-%d %H:%M')
    notifications[cur_key] = first_key
    save_notifications(notifications)

# =============================================================================
# SELENIUM HELPERS
# =============================================================================
def find_element(phase, driver, by, value):
    """Find element with error logging - raises if not found."""
    try:
        return driver.find_element(by, value)
    except NoSuchElementException as e:
        logger.error("Failed finding element at phase %s. %s", phase, e.msg)
        raise


def optional_find_element(phase, driver, by, value):
    """Find element without raising - returns None if not found."""
    try:
        return driver.find_element(by, value)
    except NoSuchElementException as e:
        logger.debug("Failed finding element at phase %s. %s", phase, e.msg)
        return None


def create_driver(headless=False):
    """Create and configure Chrome WebDriver."""
    chrome_options = webdriver.ChromeOptions()
    if headless:
        chrome_options.add_argument('--headless')

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.implicitly_wait(time_to_wait=10)
    return driver

# =============================================================================
# LOGIN FLOW
# =============================================================================
def login(driver, user_id, password):
    """Perform login to Maccabi4U."""
    delay_short = config['delay_secs_short']

    driver.get('https://online.maccabi4u.co.il/')
    time.sleep(delay_short)

    # Enter user ID
    username_field = find_element('login user_id field', driver, By.ID, 'idNumber')
    username_field.send_keys(user_id)
    time.sleep(delay_short)

    # Click continue
    id_enter_button = find_element('id login continue button', driver, By.ID, 'chooseTypeBtn')
    driver.execute_script("arguments[0].click();", id_enter_button)
    time.sleep(delay_short)

    # Switch to password login
    password_login_btn = find_element('login password button', driver, By.LINK_TEXT, 'כניסה עם סיסמה')
    driver.execute_script("arguments[0].click();", password_login_btn)
    time.sleep(delay_short)

    # Enter credentials
    username_field = find_element('login user_id field', driver, By.ID, 'idNumber2')
    username_field.send_keys(user_id)
    password_field = find_element('login password field', driver, By.ID, 'password')
    password_field.send_keys(password)
    time.sleep(delay_short)

    # Submit login
    login_button = find_element('password login continue button', driver, By.ID, 'enterWithPasswordBtn')
    driver.execute_script("arguments[0].click();", login_button)

# =============================================================================
# APPOINTMENT NAVIGATION
# =============================================================================
def select_patient(driver, patient_id):
    """Select the patient from the person picker."""
    delay_short = config['delay_secs_short']
    delay_long = config['delay_secs_long']

    time.sleep(delay_long)
    person_button = find_element('choose person button', driver, By.CLASS_NAME, 'me-lg-4')
    driver.execute_script("arguments[0].click();", person_button)

    time.sleep(delay_short)
    person_by_id = find_element('choose person by ID', driver, By.XPATH, f'//div[text()="{patient_id}"]')
    driver.execute_script("arguments[0].click();", person_by_id)


def navigate_to_doctor_appointments(driver, doctor_name):
    """Navigate to future appointments for a specific doctor."""
    delay_short = config['delay_secs_short']
    delay_long = config['delay_secs_long']

    time.sleep(delay_long)
    future_appt_btn = find_element('future appointments button', driver, By.XPATH, '//a[contains(text(), "תורים עתידיים")]')
    driver.execute_script("arguments[0].click();", future_appt_btn)

    time.sleep(delay_short)
    doctor_box = find_element('choose by doctor name', driver, By.XPATH, f'//div[@role="listitem" and .//a[contains(text(), "{doctor_name}")]]')
    driver.execute_script("arguments[0].click();", doctor_box)


def get_current_appointment(driver):
    """Extract current appointment date and time."""
    delay_long = config['delay_secs_long']
    time.sleep(delay_long)

    cur_appoint_date = None
    cur_appoint_time = None

    appt_details_class = 'src-components-FutureAppointments-AppointmentInfoDetails-AppointmentInfoDetails__text___ohiP1'
    for div in driver.find_elements(By.CLASS_NAME, appt_details_class):
        if 'יום ' in div.text:
            cur_appoint_date = div.text[-8:]
        if 'שעה ' in div.text:
            cur_appoint_time = div.text[-5:]

    if cur_appoint_date is None or cur_appoint_time is None:
        logger.error("Couldn't find current appointment date or time")
        raise ValueError("Current appointment not found")

    return datetime.strptime(f'{cur_appoint_date} {cur_appoint_time}', '%d/%m/%y %H:%M')


def open_appointment_editor(driver):
    """Open the appointment editor and prepare to see available slots."""
    delay_short = config['delay_secs_short']
    delay_long = config['delay_secs_long']

    time.sleep(delay_long)
    edit_appt_btn = find_element('edit appointment button', driver, By.XPATH, '//button[text()="שינוי תור"]')
    driver.execute_script("arguments[0].click();", edit_appt_btn)

    time.sleep(delay_long)
    regular_visit_button = optional_find_element('regular visit button', driver, By.XPATH, '//button[text()="ביקור רגיל"]')
    if regular_visit_button is not None:
        driver.execute_script("arguments[0].click();", regular_visit_button)

    time.sleep(delay_short)
    continue_button = optional_find_element('show available slots button', driver, By.XPATH, '//button[text()="המשך להצגת תורים פנויים"]')
    if continue_button is not None:
        driver.execute_script("arguments[0].click();", continue_button)


def get_first_available_appointment(driver):
    """Get the first available appointment slot."""
    delay_long = config['delay_secs_long']
    time.sleep(delay_long)

    date_class = 'src-containers-NewAppointment-PickType-TimeSelect-TimeSelect__availableForDateTitleTimeSelect___rK4Bf'
    avail_appoint = find_element('find first available date', driver, By.CLASS_NAME, date_class)
    first_avail_date = avail_appoint.text[-8:]

    avail_appoint_time = find_element('find first available time', driver, By.CLASS_NAME, 'btn-outline-secondary').text

    return datetime.strptime(f'{first_avail_date} {avail_appoint_time}', '%d/%m/%y %H:%M')

# =============================================================================
# MAIN LOGIC
# =============================================================================
def check_for_earlier_appointment():
    """Main function to check for earlier appointments."""
    # Random wait to avoid detection patterns
    n_mins = random.randint(0, config['max_minutes_wait'])
    logger.info('Waiting for %i minutes', n_mins)
    # time.sleep(n_mins * 60)

    patient_name = config['patient_name']
    patient_id = config['patient_id']
    doctor_name = config['doctor_name']

    driver = create_driver(headless=config.get('headless', False))

    try:
        # Login and navigate
        login(driver, config['user_id'], config['password'])
        select_patient(driver, patient_id)
        navigate_to_doctor_appointments(driver, doctor_name)

        # Get current and available appointments
        cur_appoint = get_current_appointment(driver)
        open_appointment_editor(driver)
        first_avail_appoint = get_first_available_appointment(driver)

        # Determine threshold for notification
        only_before_config = (
            datetime.strptime(config['only_before'], '%d/%m/%y')
            if config.get('only_before')
            else cur_appoint
        )
        threshold = min(only_before_config, cur_appoint)

        # Check if earlier appointment is available
        if first_avail_appoint < threshold:
            if was_notified(cur_appoint, first_avail_appoint):
                logger.info(
                    f'Earlier appointment found but already notified: '
                    f'{first_avail_appoint.strftime("%a %d-%m-%Y %H:%M")}'
                )
            else:
                message = (
                    f'Yay, found earlier appointment for {patient_name}, '
                    f'to {doctor_name} at {first_avail_appoint.strftime("%a %d-%m-%Y %H:%M")}'
                )
                logger.info(message)
                send_telegram_message(message=message)
                mark_notified(cur_appoint, first_avail_appoint)
        else:
            logger.info(
                f'No earlier appointment for {patient_name} to {doctor_name}. '
                f'First available: {first_avail_appoint.strftime("%a %d-%m-%Y %H:%M")} '
                f'(need before {threshold.strftime("%d/%m/%y")})'
            )

    finally:
        driver.quit()


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    check_for_earlier_appointment()
