import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import requests
import json
import yaml
import logging
from logging.handlers import RotatingFileHandler
import random

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('maccabi.log', maxBytes=10*1e6, backupCount=1)
handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s', 
                                   datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(file_formatter)
logger.addHandler(handler)

# Load config
with open("config.yaml", 'r') as stream:
    config = yaml.load(stream, yaml.SafeLoader)

delay_secs_short = config['delay_secs_short']
delay_secs_long = config['delay_secs_long']
max_minutes_wait = config['max_minutes_wait']

# random waiting
n_mins = random.randint(0, max_minutes_wait)
logger.info('Waiting for %i minutes', n_mins)
time.sleep(n_mins*60)

# Define telegram helper
def send_telegram_message(message: str,
                          chat_id: str = config['chat_id'],
                          api_key: str = config['api_key'],
                        ):

    proxies = None
    headers = {'Content-Type': 'application/json',
                'Proxy-Authorization': 'Basic base64'}
    data_dict = {'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_notification': True}
    data = json.dumps(data_dict)
    url = f'https://api.telegram.org/bot{api_key}/sendMessage'
    response = requests.post(url,
                                data=data,
                                headers=headers,
                                proxies=proxies,
                                verify=False)
    return response


def find_element(phase, driver, by, value):
# Wrapper for driver.find_element
    try:
        element = driver.find_element(by, value)
    except NoSuchElementException as e:
        logger.error("Failed finding element at phase %s. %s", phase, e.msg)
        raise
    return element


def optional_find_element(phase, driver, by, value):
# Wrapper for driver.find_element, but won't raise error if not found
    try:
        element = driver.find_element(by, value)
        return element
    except NoSuchElementException as e:
        logger.debug("Failed finding element at phase %s. %s", phase, e.msg)
    

# Setup chrome driver
chrome_options = webdriver.ChromeOptions()
chrome_options.headless = False
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                          options=chrome_options)
driver.implicitly_wait(time_to_wait=10)  # retry seconds when searching for elements


# Open the login page
driver.get('https://online.maccabi4u.co.il/')
time.sleep(delay_secs_short)
username_field = find_element('login user_id field', driver, By.ID, 'idNumber')
username_field.send_keys(config['user_id'])
time.sleep(delay_secs_short)
id_enter_button = find_element('id login continue button', driver, By.ID, 'chooseTypeBtn')
id_enter_button.click()

time.sleep(delay_secs_short)
find_element('login password button', driver, By.LINK_TEXT, 'כניסה עם סיסמה').click()

# Find the username and password input fields and enter the login credentials
time.sleep(delay_secs_short)
username_field = find_element('login user_id field', driver, By.ID, 'idNumber2')
username_field.send_keys(config['user_id'])
password_field = find_element('login password field', driver, By.ID, 'password')
password_field.send_keys(config['password'])

# Find the login button and click it to log in
time.sleep(delay_secs_short)
login_button = find_element('password login continue button', driver, By.ID, 'enterWithPasswordBtn')
login_button.click()


# click the "choose person"
time.sleep(delay_secs_long)
find_element('choose person button', driver, By.CLASS_NAME, 'me-lg-4').click()

# click on the person itself by ID number
time.sleep(delay_secs_short)
patient_name = config['patient_name']
patient_id = config['patient_id']
find_element('choose person by ID', driver, By.XPATH, f'//div[text()="{patient_id}"]').click()

time.sleep(delay_secs_long)
future_appt_btn = find_element('future appointments button', driver, By.XPATH, '//a[contains(text(), "תורים עתידיים")]')
driver.execute_script("arguments[0].click();", future_appt_btn)

time.sleep(delay_secs_short)
doctor_name = config['doctor_name']
doctor_box = find_element('choose by doctor name', driver, By.XPATH, f'//div[@role="listitem" and .//a[contains(text(), "{doctor_name}")]]')
driver.execute_script("arguments[0].click();", doctor_box)

#check current appointment date
time.sleep(delay_secs_long)
cur_appoint_date = None
cur_appoint_time = None
for div in driver.find_elements(By.CLASS_NAME, 'src-components-FutureAppointments-AppointmentInfoDetails-AppointmentInfoDetails__text___ohiP1'):
    if 'יום ' in div.text:
        cur_appoint_date = div.text[-8:]
    if 'שעה ' in div.text:
        cur_appoint_time = div.text[-5:] 

if (cur_appoint_date is None) | (cur_appoint_time is None):
    logger.error("Couldn't find current appointment date or time") 
    raise
cur_appoint = datetime.strptime(cur_appoint_date+' '+cur_appoint_time, '%d/%m/%y %H:%M')


time.sleep(delay_secs_long)
find_element('edit appointment button', driver, By.XPATH, '//button[text()="שינוי תור"]').click()

time.sleep(delay_secs_long)
regular_visit_button = optional_find_element('regular visit button', driver, By.XPATH, '//button[text()="ביקור רגיל"]')
if regular_visit_button is not None:
    regular_visit_button.click()

time.sleep(delay_secs_short)
continue_button = optional_find_element('show available slots button', driver, By.XPATH, '//button[text()="המשך להצגת תורים פנויים"]')
if continue_button is not None:
    continue_button.click()

    
#check first available date
time.sleep(delay_secs_long)
avail_appoint = find_element('find first available date', driver, By.CLASS_NAME, 'src-containers-NewAppointment-PickType-TimeSelect-TimeSelect__availableForDateTitleTimeSelect___rK4Bf')
first_avail_date = datetime.strptime(avail_appoint.text[-8:], '%d/%m/%y')

avail_appoint_time = find_element('find first available time', driver, By.CLASS_NAME, 'btn-outline-secondary').text
first_avail_appoint = datetime.strptime(avail_appoint.text[-8:] + ' ' + avail_appoint_time, '%d/%m/%y %H:%M')

only_before_config = datetime.strptime(config['only_before'], '%d/%m/%y') if config.get('only_before') else cur_appoint
threshold = min(only_before_config, cur_appoint)

if first_avail_appoint < threshold:
    message=f'Yay, found earlier appointment for {patient_name}, to {doctor_name} at {first_avail_appoint}'
    logger.info(message)
    send_telegram_message(message=message)
else:
    message=f'too bad, no earlier appointment for {patient_name} to {doctor_name}. first available appointment is at {first_avail_appoint} (need before {threshold.strftime("%d/%m/%y")})'
    logger.info(message)
    #send_telegram_message(message=message)

# Close the browser
driver.quit()