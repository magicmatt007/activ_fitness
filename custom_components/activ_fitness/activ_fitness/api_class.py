# Consider replacing request library with aiohttp
# See also: https://developers.home-assistant.io/docs/api_lib_auth
# See also: https://betterprogramming.pub/making-api-requests-in-python-aiohttp-client-vs-requests-26a7025c39a6
# See also: https://realpython.com/python-async-features/#synchronous-blocking-http-calls
# See also: https://docs.aiohttp.org/en/stable/client_quickstart.html

import datetime
import logging

mylogger = logging.getLogger("mylogger")
mylogger.setLevel(logging.DEBUG)
mylogger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
mylogger.addHandler(console_handler)
# logging.basicConfig(level=logging.DEBUG)

import base64, hashlib, re, os  # required to generate code challenge
import json
import time
import urllib.parse
import aiohttp

from .model.Bookings import Bookings
from .model.Centers import Centers
from .model.Checkins import Checkins
from .model.Checkin import Checkin
from .model.Center import Center
from .model.Courselist import Courselist
from .model.Course import Course

from .MyHTMLParser import MyHTMLParser  # Parser to scrape checkins from HTML table


class Api:
    """Api Class."""

    def __init__(self, session: aiohttp.ClientSession, ssl_context=None):
        # Session data:
        self.session = session
        self.ssl_context = ssl_context  # Optional.
        self._access_token: str = ""
        self._access_token_expires: str = ""

        # Updated via Api Endpoint 1: get_center_ids
        self.centers: list[Center] = []
        self.centers_by_id: dict = {}
        self.centers_by_name: dict = {}

        # Updated via Api Endpoint 2: get_course_list
        self.courses: list[Course] = []
        self.courses_bookable: list[Course] = []
        self.coursetitles: set = set()

        # Updated via Api Endpoint 3: get_bookings
        self.bookings: list[Course] = []

        # Updated via Api Endpoint 4: get_checkins
        self.checkins: list[Checkin] = []
        self.last_checkin: datetime.datetime | None = None
        self.checkins_in_period: int = 0

    def is_booked(self, course_no):
        """
        Check, if a given course_no is booked.

        Note:
        The 'booked' attribute in the course instance is ALWAYS false, as it comes from the publicly available get_course_list.
        It is required to check, if the course id is listed in the get_boookings.
        This is what this method is doing.
        """
        course = self.courses[course_no]
        bookings = self.bookings
        if course.course_id_tac in [b.course_id_tac for b in bookings]:
            return True
        return False

    def _generate_code_challenge(self):
        """
        Helper to generate code challenge
        """
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    async def login(self, user, pwd):
        """
        Login with user credentials.
        Returns an access token for api requests, which require one
        """

        # Step 10: Migros Login GET csrf
        url = "https://login.migros.ch/login"
        r = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug(f"\nStep 10 {url}")
        cj = self.session.cookie_jar
        csrf = ""
        for c in cj:
            if c.key == "CSRF":
                csrf = c.value

        # Step 20: Migros Login POST credentials
        url = "https://login.migros.ch/login"
        mylogger.debug(f"\nStep 20 {url}")
        payload = {"_csrf": csrf, "username": user, "password": pwd}
        r = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug(r)

        # Step 30: Migros OAuth2 authorize: get code and state for client_id and code_challenge
        url = "https://login.migros.ch/oauth2/authorize"
        mylogger.debug(f"\nStep 30 {url}")
        code_challenge, code_verifier = self._generate_code_challenge()
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
            "claims": '{"userinfo":{"sub":null,"gender":null,"given_name":null,"family_name":null,"email":null,"birthdate":null},"id_token":{"email":null}}',
        }

        r = await self.session.get(
            url, params=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug(r)
        try:
            location = r.headers["Location"]
            parse_result = urllib.parse.urlparse(location)
            query_dict = urllib.parse.parse_qs(parse_result.query)
            state = query_dict["state"][0]
            code = query_dict["code"][0]
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
            "grant_type": "authorization_code",
        }
        r = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug(r)

        content_lst = await r.json()
        id_token = content_lst["id_token"]
        access_token = content_lst["access_token"]

        # Step 50: Migros oauth2 authorize with token and client_id activfitness
        url = "https://login.migros.ch/oauth2/authorize"
        mylogger.debug(f"\nStep 50 {url}")
        code_challenge, code_verifier = self._generate_code_challenge()
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
            "claims": '{"userinfo":{"sub":null,"gender":null,"given_name":null,"family_name":null,"email":null,"birthdate":null},"id_token":{"email":null}}',
        }
        r = await self.session.get(
            url, params=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug(r)

        self._access_token = access_token
        return access_token

    def logged_in(self):
        if self._access_token != "":
            return True
        else:
            return False

    async def get_center_ids(self):
        """
        Returns a list of all centers as Center objects
        """
        url = "https://blfa-api.migros.ch/kp/api/Format?"
        r = await self.session.get(url=url, allow_redirects=False, ssl=self.ssl_context)
        mylogger.debug(f"\nGetting Centers {url}")
        content = await r.text()

        centers = Centers.from_json_str(content)
        mylogger.debug(centers.centers)
        mylogger.debug(f"\n{centers.centers_by_id}")
        mylogger.debug(f"\n{centers.centers_by_name}")

        self.centers = centers.centers
        self.centers_by_id = centers.centers_by_id
        self.centers_by_name = centers.centers_by_name
        return centers

    # async def get_course_list(self,coursetitle:str="", centerIds: list[int]=[33,23,54]):  # "BODYPUMP® 55'"
    async def get_course_list(
        self,
        coursetitles: list[str] = [""],
        centerIds: list[int] = [33, 23, 54],
        take: int = 10,
    ):  # "BODYPUMP® 55'"
        """
        Returns availble course lessons as Courselist object.
        centerIds: at least one center id must be provided
        coursetitle: If empty, all course lessons are listed. Otherwise, only the lessons of the given courses are listed
        """
        url = "https://blfa-api.migros.ch/kp/api/Courselist/all"
        mylogger.debug(f"\nGetting Coureselist {url}")

        # take = 3
        # take = 10
        coursetitles_lst = []
        for coursetitle in coursetitles:
            coursetitles_lst.extend(
                list(
                    map(
                        lambda x: {"centerId": x, "coursetitle": coursetitle}, centerIds
                    )
                )
            )
        payload = json.dumps(
            {
                "language": "de",
                "skip": 0,
                "take": take,
                "selectMethod": 2,
                "memberIdTac": 0,
                "centerIds": centerIds,
                "daytimeIds": [],
                "weekdayIds": [],
                "coursetitles": coursetitles_lst,
            }
        )
        headers = {"Content-Type": "application/json"}

        r = await self.session.post(
            url,
            data=payload,
            headers=headers,
            allow_redirects=False,
            ssl_context=self.ssl_context,
        )
        content_json_str = await r.text()

        courselist = Courselist.from_json_str(content_json_str)

        mylogger.debug("\nPrinting Courses from Objects in Courselist:")
        for c in courselist.courses:
            mylogger.debug(c)

        self.courses = courselist.courses
        self.courses_bookable = courselist.courses_bookable
        self.coursetitles = courselist.coursetitles

        return courselist

    async def get_bookings(self):
        """
        Returns booked courses as a Bookings object
        """
        # if not self.logged_in():
        #   await self.login(user=my_secrets.user,pwd=my_secrets.pwd)

        url = "https://blfa-api.migros.ch/kp/api/Booking?"
        mylogger.debug(f"\nGet bookings {url}")
        headers = {"authorization": f"Bearer {self._access_token}"}
        r = await self.session.get(
            url, headers=headers, allow_redirects=False, ssl=self.ssl_context
        )
        mylogger.debug(r.status)
        mylogger.debug(r)
        content_json_str = await r.text()
        bookings = Bookings.from_json_str(content_json_str)

        if len(bookings.courses) == 0:
            mylogger.debug("No booked courses")
        for b in bookings.courses:
            mylogger.debug(b)

        self.bookings = bookings.courses
        return bookings

    async def get_checkins(self, from_="2022-01-01", to_="2022-11-31"):
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
            "_": "1669453211792",
        }

        r = await self.session.get(
            url, params=payload, allow_redirects=True, ssl_context=self.ssl_context
        )
        mylogger.debug(r)

        parser = MyHTMLParser()
        parser.feed(await r.text())
        table = parser.tables[0]
        checkins = Checkins.from_table(table)

        mylogger.debug(f"\nVisits between {from_} and {to_}: {len(checkins.checkins)}")
        for c in checkins.checkins:
            mylogger.debug(c)

        checkins_obj = Checkins.from_table(table)

        self.checkins = checkins_obj.checkins
        self.last_checkin = checkins.last_checkin
        self.checkins_in_period = checkins.checkins_in_period

        return checkins_obj

    async def book_course(self, course_id):
        """
        Books a course
        """
        url = "https://blfa-api.migros.ch/kp/api/Booking?"
        mylogger.debug(f"\nBooking a course {url}")
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {"language": "de", "centerId": 23, "courseIdTac": course_id}

        r = await self.session.post(
            url,
            headers=headers,
            json=payload,
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        mylogger.debug(r)
        mylogger.debug(r.content)
        # time.sleep(1)

    async def cancel_course(self, booking_id):
        """
        Cancels a course
        """
        url = "https://blfa-api.migros.ch/kp/api/Booking"
        mylogger.debug(f"\nCancelling course {url}")
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {"language": "de", "bookingIdTac": booking_id}

        r = await self.session.delete(
            url,
            headers=headers,
            json=payload,
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        mylogger.debug(r)
        mylogger.debug(r.headers)
        mylogger.debug(r.content)
