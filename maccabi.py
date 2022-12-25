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

logger = logging.getLogger(__name__)
handler = RotatingFileHandler('maccabi.log', maxBytes=10*1e6, backupCount=1)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

with open("config.yaml", 'r') as stream:
    config = yaml.load(stream, yaml.SafeLoader)


delay_secs_short = config['delay_secs_short']
delay_secs_long = config['delay_secs_long']


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


chrome_options = webdriver.ChromeOptions()
chrome_options.headless = False
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                          options=chrome_options)
driver.implicitly_wait(time_to_wait=10)  # retry seconds when searching for elements

# Open the login page
driver.get('https://online.maccabi4u.co.il/')
time.sleep(delay_secs_short)
driver.find_element(By.LINK_TEXT, 'כניסה עם סיסמה').click()

# Find the username and password input fields and enter the login credentials
time.sleep(delay_secs_short)
username_field = driver.find_element(By.ID, 'identifyWithPasswordCitizenId')
username_field.send_keys(config['user_id'])

time.sleep(delay_secs_short)
password_field = driver.find_element(By.ID, 'password')
password_field.send_keys(config['password'])

# Find the login button and click it to log in
time.sleep(delay_secs_short)
login_button = driver.find_element(By.CLASS_NAME, 'validatePassword')
login_button.click()

# click the "choose person"
time.sleep(delay_secs_long)
driver.find_element(By.CLASS_NAME, 'mr-lg-4').click()

# click on the person itself by ID number
time.sleep(delay_secs_short)
patient_name = config['patient_name']
patient_id = config['patient_id']
driver.find_element(By.XPATH, f'//div[text()="{patient_id}"]').click()

time.sleep(delay_secs_long)
driver.find_element(By.XPATH, '//a[text()="תורים עתידיים"]').click()

time.sleep(delay_secs_short)
doctor_name = config['doctor_name']
driver.find_element(By.XPATH, f'//*[contains(text(), "{doctor_name}")]').click()

#check current appointment date
time.sleep(delay_secs_long)
cur_appoint_date = None
cur_appoint_time = None
for div in driver.find_elements(By.CLASS_NAME, 'AppointmentInfoDetails__text___H9zHc'):
    if 'יום ' in div.text:
        cur_appoint_date = div.text[-8:]
    if 'שעה ' in div.text:
        cur_appoint_time = div.text[-5:] 

assert (cur_appoint_date is not None) & (cur_appoint_time is not None), "couldn't find current date&time"
cur_appoint = datetime.strptime(cur_appoint_date+' '+cur_appoint_time, '%d/%m/%y %H:%M')


time.sleep(delay_secs_long)
driver.find_element(By.XPATH, '//button[text()="עריכת תור"]').click()

time.sleep(delay_secs_long)
driver.find_element(By.XPATH, '//button[text()="ביקור רגיל"]').click()

time.sleep(delay_secs_short)
try:
    continue_button = driver.find_element(By.XPATH, '//button[text()="המשך להצגת תורים פנויים"]').click()
except NoSuchElementException:
    print("didn't need to press 'continue to show appointments'")
    pass
    
#check first available date
time.sleep(delay_secs_long)
avail_appoint = driver.find_element(By.CLASS_NAME, 'TimeSelect__availableForDateTitleTimeSelect___uXc0W')
first_avail_date = datetime.strptime(avail_appoint.text[-8:], '%d/%m/%y')

avail_appoint_time_parent = driver.find_element(By.CLASS_NAME, 'RoundButtonPicker-module__scrolable___V9aPR')
avail_appoint_time = avail_appoint_time_parent.find_element(By.CSS_SELECTOR, 'button').text

first_avail_appoint = datetime.strptime(avail_appoint.text[-8:] + ' ' + avail_appoint_time, '%d/%m/%y %H:%M')

if first_avail_appoint < cur_appoint:
    print('Yay, found earlier appointment at', first_avail_appoint)
    send_telegram_message(message=f'Yay, found earlier appointment for {patient_name}, to {doctor_name} at {first_avail_appoint}')
else:
    message=f'too bad, no earlier appointment for {patient_name} to {doctor_name}. first available appointment is at {first_avail_appoint}'
    logging.debug(message)
    #send_telegram_message(message=message)

# Close the browser
driver.quit()