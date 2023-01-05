# Consider replacing request library with aiohttp
# See also: https://developers.home-assistant.io/docs/api_lib_auth
# See also: https://betterprogramming.pub/making-api-requests-in-python-aiohttp-client-vs-requests-26a7025c39a6
# See also: https://realpython.com/python-async-features/#synchronous-blocking-http-calls
# See also: https://docs.aiohttp.org/en/stable/client_quickstart.html

import logging
mylogger = logging.getLogger('mylogger')
mylogger.setLevel(logging.DEBUG)
mylogger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
mylogger.addHandler(console_handler)
# logging.basicConfig(level=logging.DEBUG)

from .model.Bookings import Bookings
from .model.Centers import Centers
from .model.Checkins import Checkins
from .model.Courselist import Courselist

import base64, hashlib,re,os # required to generate code challenge
import json
import time
import urllib.parse
import aiohttp

from .MyHTMLParser import MyHTMLParser # Parser to scrape checkins from HTML table

async def get_center_ids(session,ssl_context=None):
  """ 
  Returns a list of all centers as Center objects
  """
  url = 'https://blfa-api.migros.ch/kp/api/Format?'
  r = await session.get(url=url,allow_redirects=False,ssl=ssl_context)
  mylogger.debug(f"\nGetting Centers {url}")
  content = await r.text()

  centers_lst = Centers.from_json_str(content)
  mylogger.debug(centers_lst.centers)
  mylogger.debug(f"\n{centers_lst.centers_by_id}")
  mylogger.debug(f"\n{centers_lst.centers_by_name}")

  return centers_lst

async def get_course_list(session,coursetitle:str="", centerIds: list[int]=[33,23,54],ssl_context=None):  # "BODYPUMP® 55'"
  """
  Returns availble course lessons as Courselist object. 
  centerIds: at least one center id must be provided
  coursetitle: If empty, all course lessons are listed. Otherwise, only the lessons of the given courses are listed
  """
  url = 'https://blfa-api.migros.ch/kp/api/Courselist/all'
  mylogger.debug(f"\nGetting Coureselist {url}")

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

  r = await session.post(url,data=payload,headers=headers,allow_redirects=False,ssl_context=ssl_context)
  content_json_str = await r.text()

  courselist = Courselist.from_json_str(content_json_str)

  mylogger.debug('\nPrinting Courses from Objects in Courselist:')
  for c in courselist.courses:
    if c.bookable:
      mylogger.debug(c)
  mylogger.debug('\nPrinting Centers from Objects in Courselist:')
  for c in courselist.centers:
    mylogger.debug(c)

  return courselist

async def get_bookings(session:aiohttp.ClientSession,access_token,ssl_context=None):
  """
  Returns booked courses as a Bookings object
  """
  url = "https://blfa-api.migros.ch/kp/api/Booking?"
  mylogger.debug(f"\nGet bookings {url}")
  headers = {
    "authorization": f"Bearer {access_token}"
  }
  r = await session.get(url,headers = headers, allow_redirects=False,ssl=ssl_context)
  mylogger.debug(r.status) 
  mylogger.debug(r)
  content_json_str = await r.text()
  bookings = Bookings.from_json_str(content_json_str)

  if len(bookings.courses)==0:
    mylogger.debug('No booked courses')
  for b in bookings.courses:
    mylogger.debug(b)
  return bookings

def _generate_code_challenge():
  """
  Helper to generate code challenge
  """
  code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
  code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
  code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
  code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
  code_challenge = code_challenge.replace('=', '')
  return code_challenge,code_verifier

async def login(session:aiohttp.ClientSession,user,pwd,ssl_context=None): 
  """
  Login with user credentials.
  Returns an access token for api requests, which require one
  """

# Step 10: Migros Login GET csrf
  url = "https://login.migros.ch/login"
  r = await session.get(url,allow_redirects=False,ssl_context=ssl_context)
  mylogger.debug(f"\nStep 10 {url}")
  cj = session.cookie_jar
  csrf = ""
  for c in cj:
    if c.key == "CSRF":
      csrf = c.value

# Step 20: Migros Login POST credentials
  url = "https://login.migros.ch/login"
  mylogger.debug(f"\nStep 20 {url}")
  payload={'_csrf': csrf,
  'username': user,
  'password': pwd}
  r = await session.post(url,data=payload,allow_redirects=False,ssl_context=ssl_context)
  mylogger.debug(r)

# Step 30: Migros OAuth2 authorize: get code and state for client_id and code_challenge
  url = "https://login.migros.ch/oauth2/authorize"
  mylogger.debug(f"\nStep 30 {url}")
  code_challenge,code_verifier = _generate_code_challenge()
  state = "ewijoigrqghoinqgr"
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

  r = await session.get(url,params=payload, allow_redirects=False,ssl_context=ssl_context)
  mylogger.debug(r)
  try:
    location = r.headers['Location']
    parse_result = urllib.parse.urlparse(location)
    query_dict = urllib.parse.parse_qs(parse_result.query)
    state = query_dict['state'][0]
    code = query_dict['code'][0]
  except KeyError:
    mylogger.error("No location in response. Exiting...")
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
  r = await session.post(url,data=payload, allow_redirects=False,ssl_context=ssl_context)
  mylogger.debug(r)

  content_lst = await r.json()
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
  r = await session.get(url,params=payload, allow_redirects=False,ssl_context=ssl_context)
  mylogger.debug(r)

  return access_token


async def book_course(session:aiohttp.ClientSession,access_token,course_id,ssl_context=None):
  """
  Books a course
  """
  url= "https://blfa-api.migros.ch/kp/api/Booking?"
  mylogger.debug(f"\nBooking a course {url}")
  headers = {
    "authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
  }

  payload = {
    "language": "de",
    "centerId": 23,
    "courseIdTac": course_id
    }

  r = await session.post(url,headers = headers, json = payload, allow_redirects=False,ssl=ssl_context)
  mylogger.debug(r)
  mylogger.debug(r.content)
  # time.sleep(1)

async def cancel_course(session:aiohttp.ClientSession,access_token,booking_id,ssl_context=None):
  """
  Cancels a course
  """
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

  r = await session.delete(url,headers=headers,json=payload, allow_redirects=False,ssl=ssl_context)
  mylogger.debug(r)
  mylogger.debug(r.headers)
  mylogger.debug(r.content)

async def get_checkins(session:aiohttp.ClientSession,ssl_context=None,from_="2022-01-01",to_="2022-11-31"):
  """
  Returns a Checkins object, which contains all check ins in the given perdiod
  from: 
  to: 
  """
  url = "https://shop-schlieren.activfitness.ch/account/dashboard/checkins/"
  mylogger.debug(f"\nget_checkings {from_} to {to_}: {url}")

  payload = {
    "from": from_,
    "to": to_,
    "memberCategoryId": "11215",
    "skipAccessReservations": "1",
    "_": "1669453211792"
}

  r = await session.get(url,params=payload, allow_redirects=True,ssl_context=ssl_context)
  mylogger.debug(r)

  parser = MyHTMLParser()
  parser.feed(await r.text())
  table = parser.tables[0]
  checkins = Checkins.from_table(table)

  mylogger.debug(f"\nVisits between {from_} and {to_}: {len(checkins.checkins)}")
  for c in checkins.checkins:
    mylogger.debug(c)

  return Checkins.from_table(table)


# #####################################################
# # Playground to try API interactions:
# if __name__ == "__main__":
#   while True:
#     print("Select:")
#     print("1: List available courses in given centers")
#     print("2: List Center IDs")
#     print("3: List upcoming course schedule in given centers")
#     print("4: List bookings")
#     print("5: Book a course")
#     print("6: Cancel a course")
#     print("7: List checkins")
#     print("x: Exit")
#     selection = input('Your choice: ')
    
#     match selection:
#       case "1":
#         courselist = get_course_list(coursetitle="",centerIds=[23,33,54])
#         for c in sorted(courselist.courses_set):
#           print(c)
#       case "2":
#         center_ids = get_center_ids()
#         # print(center_ids.centers_by_id)
#         for c in center_ids.centers_by_id:
#           print(str(c).rjust(3),center_ids.centers_by_id[c])
#         selection = input("Enter centers seperated by commas: ")
#         try:
#           selected_centers = [int(id) for id in selection.split(",")]
#           print(selected_centers)
#         except:
#           print("Invalid selection")
#       case "3":
#         courselist = get_course_list(coursetitle="BODYPUMP® 55'",centerIds=[23,33,54])
#         # courselist = get_course_list(coursetitle="",centerIds=[144,34])
#         for c in courselist.courses:
#           print(c)
#         print(courselist.centers)
#       case "4":
#         s,access_token = login()
#         bookings = get_bookings(access_token=access_token)
#         print(bookings.courses)
#       case "5":
#         #### Book a course example workflow:
#         s,access_token = login() # requires a login

#         print("Book a course:")
#         courselist = get_course_list(coursetitle="BODYPUMP® 55'")
#         for index,c in enumerate(courselist.courses_bookable):
#           print(index,c)

#         select = input('Which course do you want to book? ')

#         try:
#           book_course(access_token=access_token,course_id=courselist.courses_bookable[int(select)].course_id_tac)
#           bookings = get_bookings(access_token=access_token)
#           print(bookings.courses)
#         except:
#           print("Invalid selection")
#       case "6":
#           #### Cancel a course example workflow:
#           s,access_token = login() # requires a login:

#           print("Cancel a course:")
#           bookings = get_bookings(access_token=access_token)

#           for index,b in enumerate(bookings.courses):
#             print(index,b)

#           select = input('Which course do you want to cancel? ')

#           try:
#             cancel_course(access_token=access_token,booking_id=bookings.courses[int(select)].booking_id_tac)
#             bookings = get_bookings(access_token=access_token)
#             print(bookings.courses)
#           except:
#             print("Invalid selection")
#       case "7":
#         s,access_token = login() # requires a login
#         from_ = "2022-01-01"
#         to_ = "2022-12-31"

#         tables = get_checkins(s,from_=  from_ ,to_=  to_)
#         checkins = Checkins.from_table(tables[0])
#         print(f"\nVisits between {from_} and {to_}: {len(checkins.checkins)-1}")
#         print(checkins.checkins)
#         checkins.visits_per_month()
#         checkins.visits_per_week()
#       case "x":
#         break
#       case _:
#         print("Invalid selection")