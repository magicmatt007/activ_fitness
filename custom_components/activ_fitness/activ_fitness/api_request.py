# Consider replacing request library with aiohttp
# See also: https://developers.home-assistant.io/docs/api_lib_auth
# See also: https://betterprogramming.pub/making-api-requests-in-python-aiohttp-client-vs-requests-26a7025c39a6
# See also: https://realpython.com/python-async-features/#synchronous-blocking-http-calls
# See also: https://docs.aiohttp.org/en/stable/client_quickstart.html

import logging

from activ_fitness.model.Bookings import Bookings
from activ_fitness.model.Centers import Centers
from activ_fitness.model.Checkins import Checkins
mylogger = logging.getLogger('mylogger')
mylogger.setLevel(logging.DEBUG)
mylogger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
mylogger.addHandler(console_handler)
# logging.basicConfig(level=logging.DEBUG)



import requests, pickle
import json
import time

import base64
import hashlib
import json
import os
import re
import urllib.parse
import my_secrets

from activ_fitness.model.Courselist import Courselist
from MyHTMLParser import MyHTMLParser


def get_center_ids():
  s = requests.Session()
  url = 'https://blfa-api.migros.ch/kp/api/Format?'

  r = s.get(url,allow_redirects=False)

  content = r.content.decode('UTF-8')

  centers_lst = Centers.from_json_str(content)
  mylogger.debug(centers_lst.centers)
  mylogger.debug(f"\n{centers_lst.centers_by_id}")
  mylogger.debug(f"\n{centers_lst.centers_by_name}")

  return centers_lst

def get_course_list(coursetitle:str="", centerIds: list[int]=[33,23,54]):  # "BODYPUMP® 55'"
  s = requests.Session()
  url = 'https://blfa-api.migros.ch/kp/api/Courselist/all'

  take = 3
  coursetitles_lst = list(map(lambda x: {"centerId":x, "coursetitle": coursetitle},centerIds))

  payload = json.dumps({
    "language": "de",
    "skip": 0,
    "take": take,
    "selectMethod": 2,
    "memberIdTac": 0,
    "centerIds": centerIds,
    "daytimeIds": [],
    "weekdayIds": [],
    "coursetitles": coursetitles_lst
  })
  
  headers = {
    'Content-Type': 'application/json'
  }

  r = s.post(url,data=payload,headers=headers,allow_redirects=False)
  content_json_str = r.content.decode('UTF-8')
  content_dct = json.loads(content_json_str)

  mylogger.debug('\nPrinting Courses from Objects in Courselist:')
  courselist = Courselist.from_json_str(content_json_str)
  for c in courselist.courses:
    if c.bookable:
      mylogger.debug(c)

  mylogger.debug('\nPrinting Centers from Objects in Courselist:')
  for c in courselist.centers:
    mylogger.debug(c)

  return courselist

def get_bookings(access_token):
#Get Bookings
  url = "https://blfa-api.migros.ch/kp/api/Booking?"
  mylogger.debug(f"\nGet bookings {url}")
  headers = {
    "authorization": f"Bearer {access_token}"
  }
  # r = s.get(url,headers = headers, allow_redirects=False)
  r = requests.get(url,headers = headers, allow_redirects=False)
  mylogger.debug(r)
  # print(r.text)
  mylogger.debug(r.status_code) 
  content_json_str = r.content.decode('UTF-8')
  bookings = Bookings.from_json_str(content_json_str)

  if len(bookings.courses)==0:
    mylogger.debug('No booked courses')
  for b in bookings.courses:
    mylogger.debug(b)
  return bookings
 

def _generate_code_challenge():
  code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
  code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
  code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
  code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
  code_challenge = code_challenge.replace('=', '')
  # print(f"code_challenge: {code_challenge}")
  return code_challenge,code_verifier

def login(): 
  ''' OAUTH2 with PKCE
      Inspired by: https://www.stefaanlippens.net/oauth-code-flow-pkce.html
  '''

  s = requests.Session()
  s.cookies.clear()
  try:
    with open('.cookies.pickle', 'rb') as f:
      s.cookies.update(pickle.load(f))
  except FileNotFoundError:
    print('No cookies found from previous session')

  # print_cookies(s.cookies)


  if True:
  # Step 10: Migros Login GET csrf
    url = "https://login.migros.ch/login"
    r = s.get(url,allow_redirects=False)
    mylogger.debug(f"\nStep 10 {url}")
    # print(f"\nStep 10 {url}")
    csrf = s.cookies['CSRF']

  # Step 20: Migros Login POST credentials
    url = "https://login.migros.ch/login"
    mylogger.debug(f"\nStep 20 {url}")
    payload={'_csrf': csrf,
    'username': my_secrets.user,
    'password': my_secrets.pwd}
    r = s.post(url,data=payload,allow_redirects=False)
    mylogger.debug(r)

  # Step 30: Migros OAuth2 authorize: get code and state for client_id and code_challenge
    url = "https://login.migros.ch/oauth2/authorize"
    mylogger.debug(f"\nStep 30 {url}")
    code_challenge,code_verifier = _generate_code_challenge()
    state = "fooobarbaz4"
    payload = {
      "client_id": "activ_fitness_N57kZr1PSoSMo2qp_U7Gug",
      "redirect_uri": "https://www.activfitness.ch/includes/migros-login",
      "response_type": "code",
      "scope": "openid profile email",
      "state": state,
      "code_challenge": code_challenge,
      "code_challenge_method": "S256",
      "ui_locales": "de",
      "response_mode": "query",
      "claims": '{"userinfo":{"sub":null,"gender":null,"given_name":null,"family_name":null,"email":null,"birthdate":null},"id_token":{"email":null}}'
  }

    r = s.get(url,params=payload, allow_redirects=False)
    # print(f"code_challenge: {code_challenge}, {len(code_challenge)}")
    mylogger.debug(r)
    try:
      location = r.headers['Location']
      parse_result = urllib.parse.urlparse(location)
      query_dict = urllib.parse.parse_qs(parse_result.query)
      state = query_dict['state'][0]
      code = query_dict['code'][0]
    except KeyError:
      print("No location in response. Exiting...")
      exit()


  # Step 40: Migros Login oaut2 get Token for code, client_id, client_secret
    url = "https://login.migros.ch/oauth2/token"
    mylogger.debug(f"\nStep 40 {url}")
    payload = {
      "client_id": "activ_fitness_N57kZr1PSoSMo2qp_U7Gug",
      "client_secret": "rwEYhfbT5aywLaiiG58CK8ptbPnZFc",
      "code": code,
      "redirect_uri": "https://www.activfitness.ch/includes/migros-login",
      "code_verifier": code_verifier,
      "grant_type": "authorization_code"
  }
    r = s.post(url,data=payload, allow_redirects=False)
    mylogger.debug(r)

    content = r.content.decode('UTF-8')
    content_lst = json.loads(content)

    # for c in content_lst:
    #   print(f'{c}: {content_lst[c]} \n')

    id_token = content_lst["id_token"]
    access_token = content_lst["access_token"]

  # Step 50: Migros oauth2 authorize with token and client_id activfitness
    url = "https://login.migros.ch/oauth2/authorize"
    mylogger.debug(f"\nStep 50 {url}")
    code_challenge,code_verifier = _generate_code_challenge()
    payload = {
      "client_id": "activ_fitness_N57kZr1PSoSMo2qp_U7Gug",
      "redirect_uri": "https://www.activfitness.ch/includes/migros-login",
      "response_type": "code",
      "scope": "openid profile email",
      "state": state,
      "code_challenge": code_challenge,
      "code_challenge_method": "S256",
      "promt": "none",
      "ui_locales": "de",
      "id_token": id_token,
      "response_mode": "query",
      "claims": '{"userinfo":{"sub":null,"gender":null,"given_name":null,"family_name":null,"email":null,"birthdate":null},"id_token":{"email":null}}'
  }
    r = s.get(url,params=payload, allow_redirects=False)
    mylogger.debug(r)

    with open('.cookies.pickle', 'wb') as f:
        pickle.dump(s.cookies, f)

  return s,access_token


def book_course(access_token,course_id):
# Step 250: Book course
  url= "https://blfa-api.migros.ch/kp/api/Booking?"
  mylogger.debug(f"\nStep 250 {url}")
  headers = {
    "authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
  }

  payload = {
    "language": "de",
    "centerId": 23,
    "courseIdTac": course_id
    }

  # r = s.post(url,headers = headers, json = payload, allow_redirects=False)
  r = requests.post(url,headers = headers, json = payload, allow_redirects=False)
  mylogger.debug(r)
  mylogger.debug(r.content)
  time.sleep(1)

def cancel_course(access_token,booking_id):
  url= "https://blfa-api.migros.ch/kp/api/Booking"
  mylogger.debug(f"\nCancelling course {url}")
  headers = {
    "authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"

  }

  payload = {
    "language": "de",
    "bookingIdTac": booking_id
    }

  r = requests.delete(url,headers=headers,json=payload, allow_redirects=False)
  mylogger.debug(r)
  mylogger.debug(r.headers)
  mylogger.debug(r.content)

def get_checkins(s,from_="2022-01-01",to_="2022-11-31"):
  url = "https://shop-schlieren.activfitness.ch/account/dashboard/checkins/"
  mylogger.debug(f"\nget_checkings {from_} to {to_}: {url}")

  payload = {
    "from": from_,
    "to": to_,
    "memberCategoryId": "11215",
    "skipAccessReservations": "1",
    "_": "1669453211792"
}

  r = s.get(url,params=payload, allow_redirects=True)
  mylogger.debug(r)

  parser = MyHTMLParser()
  parser.feed(r.text)
  for t in parser.tables:
    mylogger.debug(f"\nVisits between {from_} and {to_}: {len(t)-1}")
    for r in t:
      mylogger.debug(r)

  return parser.tables


#####################################################
# Playground to try API interactions:
if __name__ == "__main__":
  while True:
    print("Select:")
    print("1: List available courses in given centers")
    print("2: List Center IDs")
    print("3: List upcoming course schedule in given centers")
    print("4: List bookings")
    print("5: Book a course")
    print("6: Cancel a course")
    print("7: List checkins")
    print("x: Exit")
    selection = input('Your choice: ')
    
    match selection:
      case "1":
        courselist = get_course_list(coursetitle="",centerIds=[23,33,54])
        for c in sorted(courselist.courses_set):
          print(c)
      case "2":
        center_ids = get_center_ids()
        # print(center_ids.centers_by_id)
        for c in center_ids.centers_by_id:
          print(str(c).rjust(3),center_ids.centers_by_id[c])
        selection = input("Enter centers seperated by commas: ")
        try:
          selected_centers = [int(id) for id in selection.split(",")]
          print(selected_centers)
        except:
          print("Invalid selection")
      case "3":
        courselist = get_course_list(coursetitle="BODYPUMP® 55'",centerIds=[23,33,54])
        # courselist = get_course_list(coursetitle="",centerIds=[144,34])
        for c in courselist.courses:
          print(c)
        print(courselist.centers)
      case "4":
        s,access_token = login()
        bookings = get_bookings(access_token=access_token)
        print(bookings.courses)
      case "5":
        #### Book a course example workflow:
        s,access_token = login() # requires a login

        print("Book a course:")
        courselist = get_course_list(coursetitle="BODYPUMP® 55'")
        for index,c in enumerate(courselist.courses_bookable):
          print(index,c)

        select = input('Which course do you want to book? ')

        try:
          book_course(access_token=access_token,course_id=courselist.courses_bookable[int(select)].course_id_tac)
          bookings = get_bookings(access_token=access_token)
          print(bookings.courses)
        except:
          print("Invalid selection")
      case "6":
          #### Cancel a course example workflow:
          s,access_token = login() # requires a login:

          print("Cancel a course:")
          bookings = get_bookings(access_token=access_token)

          for index,b in enumerate(bookings.courses):
            print(index,b)

          select = input('Which course do you want to cancel? ')

          try:
            cancel_course(access_token=access_token,booking_id=bookings.courses[int(select)].booking_id_tac)
            bookings = get_bookings(access_token=access_token)
            print(bookings.courses)
          except:
            print("Invalid selection")
      case "7":
        s,access_token = login() # requires a login
        from_ = "2022-01-01"
        to_ = "2022-12-31"

        tables = get_checkins(s,from_=  from_ ,to_=  to_)
        checkins = Checkins.from_table(tables[0])
        print(f"\nVisits between {from_} and {to_}: {len(checkins.checkins)-1}")
        print(checkins.checkins)
        checkins.visits_per_month()
        checkins.visits_per_week()
      case "x":
        break
      case _:
        print("Invalid selection")