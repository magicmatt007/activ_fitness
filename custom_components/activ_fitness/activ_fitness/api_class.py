"""Api class."""

# Consider replacing request library with aiohttp
# See also: https://developers.home-assistant.io/docs/api_lib_auth
# See also: https://betterprogramming.pub/making-api-requests-in-python-aiohttp-client-vs-requests-26a7025c39a6
# See also: https://realpython.com/python-async-features/#synchronous-blocking-http-calls
# See also: https://docs.aiohttp.org/en/stable/client_quickstart.html

import base64  # required to generate code challenge
import datetime
import hashlib
import json
import logging
import os
import re
import urllib.parse

import aiohttp

from .model.bookings import Bookings
from .model.center import Center
from .model.centers import Centers
from .model.checkin import Checkin
from .model.checkins import Checkins
from .model.course import Course
from .model.courselist import Courselist
# Parser to scrape checkins from HTML table
from .my_html_parser import MyHTMLParser

mylogger = logging.getLogger("mylogger")
mylogger.setLevel(logging.DEBUG)
# mylogger.setLevel(logging.INFO)
# console_handler = logging.StreamHandler()
# mylogger.addHandler(console_handler)
# logging.basicConfig(level=logging.DEBUG)


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
        code_verifier = base64.urlsafe_b64encode(
            os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(
            code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    async def loginStep10_20_old(self, user, pwd):
        """
        Login step 10 & 20.
        """

        # Step 10: Migros Login GET csrf
        url = "https://login.migros.ch/login"
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("\nStep 10 %s", url)
        cookie_jar = self.session.cookie_jar
        csrf = ""
        for cookie in cookie_jar:
            if cookie.key == "CSRF":
                csrf = cookie.value
        mylogger.debug("status: %s", resp.status)
        mylogger.debug("csrf: %s", csrf)

        # Step 20: Migros Login POST credentials
        url = "https://login.migros.ch/login"
        mylogger.debug("\nStep 20 %s", url)
        payload = {
            "_csrf": csrf,
            "username": user,
            "password": pwd,
        }  # Chrome also sends "captcha"

        resp = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)

    def _extract_csrf(self, body):
        """Extract the csrf from the HTML code in the body."""
        search = 'meta name="_csrf"'
        p = body.find(search)
        p2 = body.find('content', p)
        csrf_start = body.find('"', p2)+1
        csrf_end = body.find('"', csrf_start+1)

        csrf_form = body[csrf_start:csrf_end]
        return csrf_form

    async def loginStep10_20(self, user, pwd):
        """
        Login step 10 & 20.
        """

        #
        # Step 10: Migros Login GET csrf
        url = "https://login.migros.ch/login/email"  # new url 2.10.24  TODO: test
        mylogger.info("\nStep 10 GET %s", url)
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )

        # Extract the csrf from the HTML code:
        body = await resp.text()
        csrf_form = self._extract_csrf(body)
        mylogger.debug("csrf_form: %s", csrf_form)

        #
        # Step 11: Migros Login POST credentials email
        url = "https://login.migros.ch/login/email"
        mylogger.info("\nStep 11 POST %s", url)
        payload = {
            "_csrf": csrf_form,
            "email": user,
        }  # Chrome also sends "captcha"

        resp = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        # header_items = resp.headers.items()
        # mylogger.debug("header: %s", header_items)
        # for h in header_items:
        #     print(h)

        location = resp.headers["Location"]
        mylogger.debug("location: %s", location)
        mylogger.debug("status: %s", resp.status)

        #
        # Step 12: Migros Login GET password
        url = "https://login.migros.ch/login/password"
        mylogger.info("\nStep 12 GET %s", url)
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)

        # Extract the csrf from the HTML code:
        body = await resp.text()
        csrf_form = self._extract_csrf(body)
        mylogger.debug("csrf_form: %s", csrf_form)

        #
        #  Step 13: Migros Login POST credentials pwd
        url = "https://login.migros.ch/login/password"
        mylogger.info("\nStep 13 POST %s", url)
        payload = {
            "_csrf": csrf_form,
            "password": pwd,
        }  # Chrome also sends "captcha"

        resp = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        location = resp.headers["Location"]
        mylogger.debug("location: %s", location)
        mylogger.debug(resp)

        #
        # Step 14: Migros Login Get account
        url = "https://login.migros.ch/"
        # url = "https://account.migros.ch/account"
        mylogger.info("\nStep 14 GET %s", url)

        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        location = resp.headers["Location"]
        mylogger.debug("location: %s", location)
        mylogger.debug(resp)
        # text = await resp.text()
        # mylogger.debug("text: %s", text)

        # Step 15: Migros Login GET
        url = "https://login.migros.ch/account/"
        blue = '\033[34m'
        reset = '\033[0m'
        msg = f"{blue}\nStep 15 GET{reset}"
        mylogger.info("\nStep 15 GET %s", url)
        # mylogger.debug("%s %s", msg, url)
        # mylogger.debug("\nStep 15 GET %s", url)
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        location = resp.headers["Location"]
        mylogger.debug("location: %s", location)

        # Step 16: Migros Login Account GET
        url = "https://account.migros.ch/account"
        mylogger.info("\nStep 16 GET %s", url)
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        # location = resp.headers["Location"]
        # mylogger.debug("location: %s", location)
        body = await resp.text()
        mylogger.debug("text: %s", body)

    async def loginCheckins(self, user, pwd):
        """
        Login with user credentials.
        Rewritten to get access to Checkins
        """

        await self.loginStep10_20(user, pwd)

        # Step 30: Migros Login GET
        url = "https://login.migros.ch/"
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("\nStep 30 %s", url)
        mylogger.debug("status: %s", resp.status)

        # Step 40: Migros Login account GET
        url = "https://login.migros.ch/account"
        resp = await self.session.get(
            url, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("\nStep 40 %s", url)
        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)
        # mylogger.debug("resp.content")
        # mylogger.debug(await resp.content.read())
        mylogger.debug(resp.headers)

    async def login(self, user, pwd):
        """
        Login with user credentials.
        Returns an access token for api requests, which require one
        """

        await self.loginStep10_20(user, pwd)

        # Step 30: Migros OAuth2 authorize: get code and state for client_id and code_challenge
        url = "https://login.migros.ch/oauth2/authorize"
        mylogger.debug("\nStep 30 %s", url)
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

        resp = await self.session.get(
            url, params=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)
        try:
            location = resp.headers["Location"]
            parse_result = urllib.parse.urlparse(location)
            query_dict = urllib.parse.parse_qs(parse_result.query)
            state = query_dict["state"][0]
            code = query_dict["code"][0]
        except KeyError as e:
            mylogger.error(f"No location in response. Exiting... {e}")
            exit()

        # Step 40: Migros Login oaut2 get Token for code, client_id, client_secret
        url = "https://login.migros.ch/oauth2/token"
        mylogger.debug("\nStep 40 %s", url)
        payload = {
            "client_id": "activ_fitness_N57kZr1PSoSMo2qp_U7Gug",
            "client_secret": "rwEYhfbT5aywLaiiG58CK8ptbPnZFc",
            "code": code,
            "redirect_uri": "https://www.activfitness.ch/includes/migros-login",
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
        }
        resp = await self.session.post(
            url, data=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)

        content_lst = await resp.json()
        id_token = content_lst["id_token"]
        access_token = content_lst["access_token"]

        mylogger.debug("access_token %s", access_token)

        # Step 50: Migros oauth2 authorize with token and client_id activfitness
        url = "https://login.migros.ch/oauth2/authorize"
        mylogger.debug("\nStep 50 %s", url)
        code_challenge, code_verifier = self._generate_code_challenge()
        payload = {
            "client_id": "activ_fitness_N57kZr1PSoSMo2qp_U7Gug",
            "redirect_uri": "https://www.activfitness.ch/includes/migros-login",
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "none",
            "ui_locales": "de",
            "id_token": id_token,
            "response_mode": "query",
            "claims": '{"userinfo":{"sub":null,"gender":null,"given_name":null,"family_name":null,"email":null,"birthdate":null},"id_token":{"email":null}}',
        }
        resp = await self.session.get(
            url, params=payload, allow_redirects=False, ssl_context=self.ssl_context
        )
        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)

        self._access_token = access_token
        return access_token

    def logged_in(self):
        """WIP."""
        if self._access_token != "":
            return True
        else:
            return False

    async def get_center_ids(self):
        """
        Returns a list of all centers as Center objects
        """
        url = "https://blfa-api.migros.ch/kp/api/Format?"
        resp = await self.session.get(
            url=url, allow_redirects=False, ssl=self.ssl_context
        )
        mylogger.debug("\nGetting Centers %s", url)
        content = await resp.text()

        centers = Centers.from_json_str(content)
        mylogger.debug(centers.centers)
        mylogger.debug("\n%s", centers.centers_by_id)
        mylogger.debug("\n%s", centers.centers_by_name)

        self.centers = centers.centers
        self.centers_by_id = centers.centers_by_id
        self.centers_by_name = centers.centers_by_name
        return centers

    # async def get_course_list(self,coursetitle:str="", centerIds: list[int]=[33,23,54]):  # "BODYPUMP® 55'"
    async def get_course_list(
        self,
        center_ids: list[int],
        coursetitles: list[str] = [],
        take: int = 10,
    ):  # "BODYPUMP® 55'"
        """
        Returns available course lessons as Courselist object.
        centerIds: at least one center id must be provided
        coursetitle: If empty, all course lessons are listed. Otherwise, only the lessons of the given courses are listed
        """
        url = "https://blfa-api.migros.ch/kp/api/Courselist/all"
        mylogger.debug("\nGetting Coureselist %s", url)

        # take = 3
        # take = 10
        coursetitles_lst = []
        for coursetitle in coursetitles:
            coursetitles_lst.extend(
                list(
                    map(
                        lambda x: {"centerId": x, "coursetitle": coursetitle},
                        center_ids,
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
                "centerIds": center_ids,
                "daytimeIds": [],
                "weekdayIds": [],
                "coursetitles": coursetitles_lst,
            }
        )
        headers = {"Content-Type": "application/json"}

        resp = await self.session.post(
            url,
            data=payload,
            headers=headers,
            allow_redirects=False,
            ssl_context=self.ssl_context,
        )
        content_json_str = await resp.text()

        courselist = Courselist.from_json_str(content_json_str)

        mylogger.debug("\nPrinting Courses from Objects in Courselist:")
        for course in courselist.courses:
            mylogger.debug(course)

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
        mylogger.debug("\nGet bookings %s", url)
        headers = {"authorization": f"Bearer {self._access_token}"}
        resp = await self.session.get(
            url, headers=headers, allow_redirects=False, ssl=self.ssl_context
        )
        mylogger.debug(resp.status)
        mylogger.debug(resp)
        content_json_str = await resp.text()
        bookings = Bookings.from_json_str(content_json_str)

        if len(bookings.courses) == 0:
            mylogger.debug("No booked courses")
        for course in bookings.courses:
            mylogger.debug(course)

        self.bookings = bookings.courses
        return bookings

    async def get_checkins(self, from_="2022-11-23", to_="2022-11-31"):
        """
        Returns a Checkins object, which contains all check ins in the given perdiod
        from:
        to:
        """
        url = "https://shop-schlieren.activfitness.ch/account/dashboard/checkins/"
        #      https://shop-schlieren.activfitness.ch/account/dashboard/checkins/?from=2022-11-23&to=2023-04-23&memberCategoryId=11215&contract=1337719&skipAccessReservations=1&_=1682251126640
        mylogger.debug("\nget_checkings %s to %s: %s", from_, to_, url)

        payload = {
            "from": from_,
            "to": to_,
            "memberCategoryId": "11215",
            "contract": "1337719",
            "skipAccessReservations": "1",
            "_": "1682251126640",
            # "_": "1669453211792",
        }

        resp = await self.session.get(
            url, params=payload, allow_redirects=True, ssl_context=self.ssl_context
        )

        mylogger.debug("status: %s", resp.status)
        mylogger.debug(resp)

        parser = MyHTMLParser()
        body = await resp.text()
        # mylogger.debug(body)
        parser.feed(await resp.text())
        table = parser.tables[0]
        checkins = Checkins.from_table(table)

        mylogger.debug(
            "\nVisits between %s and %s: %s", from_, to_, len(
                checkins.checkins)
        )

        for checkin in checkins.checkins:
            mylogger.debug(checkin)

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
        mylogger.debug("\nBooking a course %s", url)
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {"language": "de", "centerId": 23, "courseIdTac": course_id}

        resp = await self.session.post(
            url,
            headers=headers,
            json=payload,
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        mylogger.debug(resp)
        mylogger.debug(resp.content)
        # time.sleep(1)

    async def cancel_course(self, booking_id):
        """
        Cancels a course
        """
        url = "https://blfa-api.migros.ch/kp/api/Booking"
        mylogger.debug("\nCancelling course %s", url)
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload = {"language": "de", "bookingIdTac": booking_id}

        resp = await self.session.delete(
            url,
            headers=headers,
            json=payload,
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        mylogger.debug(resp)
        mylogger.debug(resp.headers)
        mylogger.debug(resp.content)
