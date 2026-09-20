"""Api class.

Activ Fitness moved their mobile backend from a dedicated Migros API
(blfa-api.migros.ch) to the "Netpulse" white-label fitness-app platform
(https://activfitness.netpulse.com, shared with EGYM). Login is still Migros
OAuth2/PKCE underneath, but the resulting Migros tokens now have to be handed
to Netpulse's own login endpoint to get a Netpulse session, and course
listing/booking happens against Netpulse's REST API instead of blfa-api.

The Migros OAuth client_id/secret used here are not fixed: the app fetches
them at runtime from the (unauthenticated) /np/brand/description endpoint, so
we do the same instead of hardcoding them - if Migros ever rotates the
client, this integration keeps working without a code change.

The Migros login page is behind Cloudflare bot protection and throttles scripted
email/password logins hard, so the refresh token from the first login is kept and
reused (see Api.login) instead of logging in with the password again.
"""

import asyncio
import base64
import datetime
import hashlib
import json
import logging
import re
import os
import time
import urllib.parse
import uuid

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

MIGROS_BASE = "https://login.migros.ch"
NETPULSE_BASE = "https://activfitness.netpulse.com"
REDIRECT_SCHEME = "com.mobile.activfitness"

# Matches the installed Activ Fitness app version this integration was reverse
# engineered against. Only used to build headers/params the backend expects;
# it does not need to track the real app version exactly.
APP_VERSION = "2.3.3"
APP_VERSION_CODE = "113"


def _numeric_server_encoded_app_version(version: str) -> str:
    """Reimplements the app's SystemConfigKt.toNumericServerEncodedAppVersion()."""
    parts = version.split(".")
    encoded = parts[0]
    for part in parts[1:]:
        if len(part) == 1:
            encoded += "0"
        encoded += part
    if len(parts) == 2:
        encoded += "00"
    return encoded


class _Cookies:
    """Minimal cookie store that sends Set-Cookie values back verbatim.

    aiohttp's cookie jar re-serialises cookie values, which breaks the shop's
    signed session cookies (NSESSIONID + NSESSIONID.sig): the shop then keeps
    answering as if logged out and never issues its logged-in OSESSIONID.
    Cookies are kept per site: "migros" (login.migros.ch) and "shop".
    """

    def __init__(self, state: dict | None = None):
        self.jars: dict[str, dict[str, str]] = {
            "migros": dict((state or {}).get("migros") or {}),
            "shop": {},
        }

    @staticmethod
    def _site(url: str) -> str:
        host = urllib.parse.urlparse(url).hostname or ""
        return "migros" if host.endswith("migros.ch") else "shop"

    def header(self, url: str) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.jars[self._site(url)].items())

    def update(self, url: str, resp) -> None:
        jar = self.jars[self._site(url)]
        for raw in resp.headers.getall("Set-Cookie", []):
            first, *attrs = [part.strip() for part in raw.split(";")]
            name, _, value = first.partition("=")
            if value == "" or "max-age=0" in [a.lower() for a in attrs]:
                jar.pop(name, None)
            else:
                jar[name] = value


class Api:
    """Api Class."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        ssl_context=None,
        token_state: dict | None = None,
        token_update_callback=None,
        checkins_state: dict | None = None,
        checkins_state_callback=None,
    ):
        """Create the client.

        token_state: previously exported Migros tokens (see export_token_state()).
            If it holds a refresh token, login() re-authenticates by refreshing
            that token instead of doing the Migros email/password login.
        token_update_callback: called (synchronously) with the new token state
            whenever the stored tokens change, so the caller can persist them.
        checkins_state / checkins_state_callback: the same for the Migros web
            session cookies used for checkins (see export_checkins_state()).
        """
        # Session data:
        self.session = session
        self.ssl_context = ssl_context  # Optional.
        self._device_uuid = str(uuid.uuid4())

        self._refresh_token: str = (token_state or {}).get("refresh_token") or ""
        self._id_token: str = (token_state or {}).get("id_token") or ""
        self._token_update_callback = token_update_callback

        self._cookies = _Cookies(checkins_state)
        self._checkins_state_callback = checkins_state_callback

        self._session_cookie: str = ""  # "JSESSIONID=..." once logged in
        self._session_expires_at: float = 0  # epoch seconds; see login()/logged_in()
        self._access_token: str = ""  # kept for backwards-compat with logged_in()
        self._exerciser_uuid: str = ""
        self._home_club_uuid: str = ""
        self._home_club_name: str = ""

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
        Unlike the old Migros API, get_course_list's response already includes an
        accurate per-class 'booked' flag (from Netpulse's attendeeDetails, since we
        pass exerciserUuid) once logged in, so this can be read directly.
        """
        return self.courses[course_no].booked

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

    def _extract_csrf(self, body):
        """Extract the csrf from the HTML code in the body."""
        search = 'meta name="_csrf"'
        p = body.find(search)
        p2 = body.find('content', p)
        csrf_start = body.find('"', p2)+1
        csrf_end = body.find('"', csrf_start+1)

        csrf_form = body[csrf_start:csrf_end]
        return csrf_form

    def _np_headers(self):
        """Headers required by every Netpulse API call (see HeadersInterceptor in the app).

        Without these, the backend returns a bare {"message":"General Error"} 500.
        """
        headers = {
            "X-NP-API-Version": "1.5",
            "X-NP-APP-Version": APP_VERSION,
            "X-NP-User-Agent": (
                f"clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid={self._device_uuid}; "
                f"applicationName=Activ Fitness; applicationVersion={APP_VERSION}; "
                f"applicationVersionCode={APP_VERSION_CODE}"
            ),
        }
        if self._session_cookie:
            headers["Cookie"] = self._session_cookie
        return headers

    async def _fetch_brand_config(self):
        """Fetch the Migros OAuth client config from the public /np/brand/description endpoint."""
        url = f"{NETPULSE_BASE}/np/brand/description"
        params = {"appVersion": _numeric_server_encoded_app_version(APP_VERSION)}
        resp = await self.session.get(
            url, params=params, allow_redirects=False, ssl=self.ssl_context
        )
        body = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"Could not fetch brand config ({resp.status}): {body}")

        data = json.loads(body)
        migros_login = data["featurePreferences"]["migrosLogin"]
        client_id, client_secret = base64.b64decode(
            migros_login["clientAndroid"]
        ).decode("utf-8").split(":", 1)

        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_url": migros_login["authUrl"],
            "token_url": migros_login["tokenUrl"],
            "redirect_uri": f"{REDIRECT_SCHEME}://{migros_login['redirectPattern']}",
            "scope": migros_login["scopes"],
            "claims": migros_login["claims"],
        }

    async def _migros_login(self, user, pwd):
        """Authenticate the aiohttp session against Migros with email + password."""
        url = f"{MIGROS_BASE}/login/email"
        resp = await self.session.get(url, allow_redirects=False, ssl=self.ssl_context)
        body = await resp.text()
        csrf = self._extract_csrf(body)

        resp = await self.session.post(
            url,
            data={"_csrf": csrf, "email": user},
            allow_redirects=False,
            ssl=self.ssl_context,
        )

        url = f"{MIGROS_BASE}/login/password"
        resp = await self.session.get(url, allow_redirects=False, ssl=self.ssl_context)
        body = await resp.text()
        csrf = self._extract_csrf(body)

        resp = await self.session.post(
            url,
            data={"_csrf": csrf, "password": pwd},
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        if resp.status not in (302, 303):
            body = await resp.text()
            raise RuntimeError(
                f"Migros login failed (status {resp.status}): {body[:500]}"
            )

    async def _oauth_authorize(self, brand):
        """Perform the OAuth2 PKCE authorize step against Migros."""
        code_challenge, code_verifier = self._generate_code_challenge()
        state = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8").rstrip("=")
        params = {
            "client_id": brand["client_id"],
            "redirect_uri": brand["redirect_uri"],
            "response_type": "code",
            "scope": brand["scope"],
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "ui_locales": "de",
            "response_mode": "query",
            "claims": brand["claims"],
        }
        resp = await self.session.get(
            brand["auth_url"], params=params, allow_redirects=False, ssl=self.ssl_context
        )
        location = resp.headers.get("Location")
        if not location:
            body = await resp.text()
            raise RuntimeError(
                f"Migros OAuth authorize did not redirect (status {resp.status}): {body[:500]}"
            )

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        if "error" in qs:
            raise RuntimeError(f"Migros OAuth authorize returned an error: {qs}")

        code = qs.get("code", [None])[0]
        returned_state = qs.get("state", [None])[0]
        if not code or returned_state != state:
            raise RuntimeError("Migros OAuth authorize did not return a valid code")

        return code, code_verifier

    async def _oauth_token(self, brand, code, code_verifier):
        """Exchange the authorization code for Migros tokens."""
        basic_auth = base64.b64encode(
            f"{brand['client_id']}:{brand['client_secret']}".encode("utf-8")
        ).decode("utf-8")
        payload = {
            "client_id": brand["client_id"],
            "code": code,
            "redirect_uri": brand["redirect_uri"],
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
        }
        resp = await self.session.post(
            brand["token_url"],
            data=payload,
            headers={"Authorization": f"Basic {basic_auth}"},
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        body = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"Migros OAuth token exchange failed ({resp.status}): {body[:500]}")
        return json.loads(body)

    async def _netpulse_migros_login(self, tokens):
        """Hand the Migros tokens to Netpulse to establish a Netpulse session."""
        expires_at_ms = int((time.time() + tokens.get("expires_in", 0)) * 1000)
        payload = {
            "accessToken": tokens.get("access_token"),
            "refreshToken": tokens.get("refresh_token"),
            "idToken": tokens.get("id_token"),
            "expiresAt": expires_at_ms,
        }
        resp = await self.session.post(
            f"{NETPULSE_BASE}/np/exerciser/migros/login",
            json=payload,
            headers=self._np_headers(),
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        body = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"Netpulse login failed ({resp.status}): {body[:500]}")

        session_cookie = None
        session_max_age = None
        for cookie_name, cookie in resp.cookies.items():
            if "JSESSIONID" in cookie_name.upper():
                session_cookie = f"{cookie_name}={cookie.value}"
                session_max_age = cookie.get("max-age")
        if not session_cookie:
            raise RuntimeError("Netpulse login succeeded but returned no session cookie")

        data = json.loads(body)
        self._session_cookie = session_cookie
        self._access_token = session_cookie  # kept for logged_in()/backwards compat
        self._exerciser_uuid = data["uuid"]
        self._home_club_uuid = data.get("homeClubUuid", "")
        self._home_club_name = data.get("homeClubName", "")

        # Session cookies come back with e.g. "Max-Age=10800" (3h). Cache that expiry
        # (with a safety margin) so login() doesn't have to re-authenticate with
        # Migros on every coordinator refresh - it only needs to happen a few times
        # a day, same as staying logged in on the website/app.
        try:
            lifetime_seconds = int(session_max_age)
        except (TypeError, ValueError):
            lifetime_seconds = 3 * 60 * 60  # fall back to the observed default
        safety_margin_seconds = 5 * 60
        self._session_expires_at = time.time() + max(lifetime_seconds - safety_margin_seconds, 0)

    def export_token_state(self) -> dict:
        """Tokens worth persisting so a later Api instance can skip the email/password login."""
        return {"refresh_token": self._refresh_token, "id_token": self._id_token}

    def _remember_tokens(self, tokens: dict):
        """Keep the latest refresh/id token and notify the owner if they changed.

        Refresh responses may omit either token (or rotate the refresh token), so
        anything missing keeps its previous value - same as AppAuth does in the app.
        """
        refresh_token = tokens.get("refresh_token") or self._refresh_token
        id_token = tokens.get("id_token") or self._id_token
        changed = (refresh_token, id_token) != (self._refresh_token, self._id_token)
        self._refresh_token, self._id_token = refresh_token, id_token
        if changed and self._token_update_callback:
            self._token_update_callback(self.export_token_state())

    def _forget_refresh_token(self):
        self._refresh_token = ""
        if self._token_update_callback:
            self._token_update_callback(self.export_token_state())

    async def _refresh_migros_tokens(self, brand):
        """Get fresh Migros tokens from the stored refresh token (no email/password login).

        Returns the new token dict, or None if Migros no longer accepts the
        refresh token (caller should fall back to the full login). Any other
        failure (rate limiting, server error, ...) raises instead: falling back
        to the full login would only add more load on the Cloudflare-protected
        login page, which is exactly what this path exists to avoid.
        """
        basic_auth = base64.b64encode(
            f"{brand['client_id']}:{brand['client_secret']}".encode("utf-8")
        ).decode("utf-8")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": brand["client_id"],
        }
        resp = await self.session.post(
            brand["token_url"],
            data=payload,
            headers={"Authorization": f"Basic {basic_auth}"},
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        body = await resp.text()
        if resp.status in (400, 401):
            mylogger.warning(
                "Migros refused the stored refresh token (%s); falling back to full login",
                resp.status,
            )
            self._forget_refresh_token()
            return None
        if resp.status != 200:
            raise RuntimeError(f"Migros token refresh failed ({resp.status}): {body[:500]}")

        tokens = json.loads(body)
        tokens["refresh_token"] = tokens.get("refresh_token") or self._refresh_token
        tokens["id_token"] = tokens.get("id_token") or self._id_token
        return tokens

    async def login(self, user, pwd, force=False):
        """
        Login with user credentials.

        Establishes a Netpulse session from Migros tokens (see module docstring)
        and returns the session cookie, which subsequent calls rely on.

        To keep the load on Migros's (Cloudflare-protected) login page to a
        minimum, this uses the cheapest route that works:
          1. A still-valid Netpulse session (~3h cookie): nothing is requested at
             all, unless force=True.
          2. A stored Migros refresh token: refresh it and hand the new tokens to
             Netpulse. No email/password login involved.
          3. Only if there is no usable refresh token: the full Migros
             email/password + OAuth2/PKCE login. It yields a refresh token (the
             "offline_access" scope), so this should be needed rarely.
        """
        if not force and self.logged_in():
            mylogger.debug("Reusing existing Netpulse session (expires in %.0fs)", self._session_expires_at - time.time())
            return self._session_cookie

        brand = await self._fetch_brand_config()

        if self._refresh_token:
            tokens = await self._refresh_migros_tokens(brand)
            if tokens is not None:
                # Persist first: a rotated refresh token is lost if Netpulse fails below.
                self._remember_tokens(tokens)
                try:
                    await self._netpulse_migros_login(tokens)
                except RuntimeError as err:
                    mylogger.warning(
                        "Netpulse rejected the refreshed Migros tokens (%s); falling back to full login",
                        err,
                    )
                else:
                    mylogger.debug("Logged in via refresh token as exerciser %s", self._exerciser_uuid)
                    return self._session_cookie

        await self._migros_login(user, pwd)
        code, code_verifier = await self._oauth_authorize(brand)
        tokens = await self._oauth_token(brand, code, code_verifier)
        self._remember_tokens(tokens)
        await self._netpulse_migros_login(tokens)

        mylogger.debug("Logged in as exerciser %s, home club %s", self._exerciser_uuid, self._home_club_name)
        return self._session_cookie

    def logged_in(self):
        """Return whether login() has established a still-valid Netpulse session."""
        return bool(self._session_cookie) and time.time() < self._session_expires_at

    def _invalidate_session(self):
        """Force the next login() call to re-authenticate instead of reusing the cookie."""
        self._session_cookie = ""
        self._access_token = ""
        self._session_expires_at = 0

    async def get_center_ids(self):
        """
        Returns a list of all Activ Fitness clubs as Center objects.

        Public endpoint, no login required.
        """
        url = f"{NETPULSE_BASE}/np/company/children"
        resp = await self.session.get(
            url, headers=self._np_headers(), allow_redirects=False, ssl=self.ssl_context
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

    async def get_course_list(
        self,
        center_ids: list[str],
        coursetitles: list[str] = [],
        take: int = 10,
    ):
        """
        Returns available course lessons as Courselist object.

        center_ids: club UUIDs (see get_center_ids/centers_by_id), at least one required.
        coursetitles: if empty, all course lessons are listed. Otherwise, only the
            lessons of the given course titles are kept (filtered client-side, the
            new API has no server-side title filter).
        """
        active_filters = {title for title in coursetitles if title}
        now_ms = int(time.time() * 1000)
        window_ms = 14 * 24 * 60 * 60 * 1000  # look 14 days ahead

        all_courses: list[Course] = []
        for club_uuid in center_ids:
            center_name = self.centers_by_id.get(club_uuid, club_uuid)
            url = f"{NETPULSE_BASE}/np/company/{club_uuid}/classes"
            params = {
                "startDateTime": now_ms,
                "endDateTime": now_ms + window_ms,
            }
            if self._exerciser_uuid:
                params["exerciserUuid"] = self._exerciser_uuid

            mylogger.debug("\nGetting Courselist %s", url)
            resp = await self.session.get(
                url,
                params=params,
                headers=self._np_headers(),
                allow_redirects=False,
                ssl=self.ssl_context,
            )
            content_json_str = await resp.text()
            if resp.status == 401:
                self._invalidate_session()
            if resp.status != 200:
                mylogger.error("get_course_list failed for club %s (%s): %s", club_uuid, resp.status, content_json_str)
                continue

            classes_json = json.loads(content_json_str)
            all_courses.extend(
                Course.from_groupx_json(c, center_name) for c in classes_json
            )

        if active_filters:
            filtered_courses = [c for c in all_courses if c.title in active_filters]
        else:
            filtered_courses = all_courses

        filtered_courses.sort(key=lambda c: c.start_obj)

        self.coursetitles = {c.title for c in filtered_courses}

        display_courses = filtered_courses[:take] if take else filtered_courses

        await self._refine_bookable(display_courses)

        mylogger.debug("\nPrinting Courses from Objects in Courselist:")
        for course in display_courses:
            mylogger.debug(course)

        self.courses = display_courses
        self.courses_bookable = [c for c in display_courses if c.bookable]

        return Courselist(display_courses)

    async def _refine_bookable(self, courses: list[Course]):
        """Set Course.bookable from the API's single-class lookup (one request per class).

        The class list has neither the booking window nor availableActions, so
        this is the only place the API says whether a class can be booked now.
        A failed lookup keeps the value from the last successful poll, or
        "not bookable" if there is none: never claim bookable without the API.
        """
        previous = {c.course_id_tac: c.bookable for c in self.courses}

        if not self._exerciser_uuid:
            return

        async def refine(course: Course):
            course.bookable = previous.get(course.course_id_tac, False)
            url = f"{NETPULSE_BASE}/np/company/{course.center_id}/class/{course.course_id_tac}"
            try:
                resp = await self.session.get(
                    url,
                    params={"exerciserUuid": self._exerciser_uuid},
                    headers=self._np_headers(),
                    allow_redirects=False,
                    ssl=self.ssl_context,
                )
                if resp.status == 401:
                    self._invalidate_session()
                elif resp.status == 200:
                    course.apply_details(json.loads(await resp.text()))
                else:
                    mylogger.debug("Class details %s failed (%s)", url, resp.status)
            except (aiohttp.ClientError, ValueError) as err:
                mylogger.debug("Class details %s failed: %s", url, err)

        await asyncio.gather(*(refine(course) for course in courses))

    async def get_bookings(self):
        """
        Returns booked courses as a Bookings object.

        Primarily sourced from get_course_list's results (each class already
        carries an accurate per-class 'booked' flag once logged in - see
        is_booked()), since GET /np/exerciser/{uuid}/schedule has proven
        unreliable in practice (observed returning nothing/404 even for a
        real, confirmed booking). The schedule endpoint is still queried as a
        best-effort way to pick up bookings outside the centers/date range
        get_course_list was called with, and merged in when it does return data.
        """
        schedule_courses: list[Course] = []

        if self._exerciser_uuid:
            url = f"{NETPULSE_BASE}/np/exerciser/{self._exerciser_uuid}/schedule"
            mylogger.debug("\nGet bookings %s", url)
            now_ms = int(time.time() * 1000)
            params = {
                "startDateTime": now_ms,
                "endDateTime": now_ms + 30 * 24 * 60 * 60 * 1000,
            }
            if self._home_club_uuid:
                params["clubUuid"] = self._home_club_uuid

            resp = await self.session.get(
                url,
                params=params,
                headers=self._np_headers(),
                allow_redirects=False,
                ssl=self.ssl_context,
            )
            mylogger.debug(resp.status)

            if resp.status == 401:
                self._invalidate_session()
            elif resp.status == 404:
                # Netpulse returns a 404 "externalServiceFailure.notFound" instead of
                # an empty list when there are no bookings in the requested window -
                # this has also been observed even when a booking DOES exist.
                mylogger.debug("Schedule endpoint returned 404 (treated as no data)")
            elif resp.status != 200:
                content_json_str = await resp.text()
                mylogger.error("get_bookings schedule fetch failed (%s): %s", resp.status, content_json_str)
            else:
                classes_json = json.loads(await resp.text())
                schedule_courses = Bookings.from_groupx_json_list(
                    classes_json, self.centers_by_id
                ).courses

        # Merge with booked courses already known from get_course_list, since the
        # schedule endpoint alone cannot be trusted (see docstring).
        merged_by_id = {c.course_id_tac: c for c in schedule_courses}
        for course in self.courses:
            if course.booked:
                merged_by_id.setdefault(course.course_id_tac, course)

        bookings = Bookings(list(merged_by_id.values()))

        if len(bookings.courses) == 0:
            mylogger.debug("No booked courses")
        for course in bookings.courses:
            mylogger.debug(course)

        self.bookings = bookings.courses
        return bookings

    # -- Checkins (legacy shop website) ------------------------------------
    #
    # Checkins are not part of the Netpulse API (its check-in history only holds
    # QR-code check-ins). They come from the club's shop website, which has its
    # own Migros OAuth client. Logging in there needs a Migros *web* session, so:
    #   1. reuse the shop session held in memory (no request but the data one),
    #   2. else redo the shop's SSO handoff with the stored Migros web cookies
    #      (three GETs, no password),
    #   3. else do the Migros email/password login (only if that session is gone).

    def export_checkins_state(self) -> dict:
        """Return what must be persisted to skip the password login (Migros web cookies)."""
        return {"migros": dict(self._cookies.jars["migros"])}

    def _shop_base(self) -> str:
        """Base URL of the shop of the user's home club (checkins are account-wide)."""
        name = (self._home_club_name or "").lower().replace("activ fitness", "")
        for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("é", "e"), ("è", "e")):
            name = name.replace(src, dst)
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "schlieren"
        return f"https://shop-{slug}.activfitness.ch"

    def _plain_http(self):
        """Client session without a cookie jar, sharing the connection pool.

        Cookies are handled by _Cookies: aiohttp's cookie jar breaks the shop's
        signed session cookies (see _Cookies).
        """
        return aiohttp.ClientSession(
            cookie_jar=aiohttp.DummyCookieJar(),
            connector=self.session.connector,
            connector_owner=False,
        )

    async def _web_get(self, http, url):
        resp = await http.get(
            url,
            headers={"Cookie": self._cookies.header(url)},
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        self._cookies.update(url, resp)
        return resp

    async def _web_post(self, http, url, data):
        resp = await http.post(
            url,
            data=data,
            headers={"Cookie": self._cookies.header(url)},
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        self._cookies.update(url, resp)
        return resp

    async def _web_follow(self, http, url, max_hops=10):
        """GET url and follow redirects by hand (so cookies stay under our control)."""
        for _ in range(max_hops):
            resp = await self._web_get(http, url)
            location = resp.headers.get("Location")
            if resp.status not in (301, 302, 303, 307, 308) or not location:
                return resp
            url = urllib.parse.urljoin(url, location)
        raise RuntimeError("Too many redirects")

    async def _shop_sso(self, http) -> bool:
        """Log into the shop through the Migros web session; True if it worked."""
        self._cookies.jars["shop"].clear()
        await self._web_follow(http, f"{self._shop_base()}/account/login/")
        # The shop issues OSESSIONID only once it has accepted the Migros login.
        return "OSESSIONID" in self._cookies.jars["shop"]

    async def _migros_web_login(self, http, user, pwd):
        """Migros email/password login, keeping the resulting web session cookies."""
        self._cookies.jars["migros"].clear()
        url = f"{MIGROS_BASE}/login/email"
        resp = await self._web_get(http, url)
        csrf = self._extract_csrf(await resp.text())
        await self._web_post(http, url, {"_csrf": csrf, "email": user})

        url = f"{MIGROS_BASE}/login/password"
        resp = await self._web_get(http, url)
        csrf = self._extract_csrf(await resp.text())
        resp = await self._web_post(http, url, {"_csrf": csrf, "password": pwd})
        if resp.status not in (302, 303):
            raise RuntimeError(f"Migros web login failed (status {resp.status})")
        if self._checkins_state_callback:
            self._checkins_state_callback(self.export_checkins_state())

    async def _fetch_checkins_html(self, http, from_, to_):
        params = urllib.parse.urlencode(
            {"from": from_, "to": to_, "skipAccessReservations": "1"}
        )
        url = f"{self._shop_base()}/account/dashboard/checkins/?{params}"
        resp = await self._web_get(http, url)
        # Not logged in: the shop redirects away instead of answering.
        return await resp.text() if resp.status == 200 else None

    async def get_checkins(self, user=None, pwd=None, from_=None, to_=None):
        """
        Returns a Checkins object with all check-ins in the given period.

        Defaults to everything up to today. user/pwd are only used when the
        Migros web session is gone (see the notes above).
        """
        from_ = from_ or "2020-01-01"
        to_ = to_ or datetime.date.today().isoformat()

        async with self._plain_http() as http:
            html = await self._fetch_checkins_html(http, from_, to_)
            if html is None:
                mylogger.debug("Shop session missing, doing the SSO handoff")
                if not await self._shop_sso(http):
                    if not (user and pwd):
                        raise RuntimeError("Shop login needs credentials")
                    mylogger.debug("Migros web session gone, doing the password login")
                    await self._migros_web_login(http, user, pwd)
                    if not await self._shop_sso(http):
                        raise RuntimeError("Shop login failed")
                html = await self._fetch_checkins_html(http, from_, to_)
                if html is None:
                    raise RuntimeError("Shop refused the checkins request after login")

        parser = MyHTMLParser()
        parser.feed(html)
        # No check-ins in the period: the shop answers with a message, no table.
        table = parser.tables[0] if parser.tables else []
        checkins_obj = Checkins.from_table(table)

        self.checkins = checkins_obj.checkins
        self.last_checkin = checkins_obj.last_checkin
        self.checkins_in_period = checkins_obj.checkins_in_period
        mylogger.debug("Check-ins between %s and %s: %s", from_, to_, len(self.checkins))
        return checkins_obj

    async def book_course(self, course_id):
        """
        Books a course.

        course_id is the Netpulse class id (Course.course_id_tac), as returned by
        get_course_list. The club it belongs to is looked up from self.courses.
        """
        course = next((c for c in self.courses if c.course_id_tac == course_id), None)
        if course is None:
            raise ValueError(f"Unknown course_id {course_id}; call get_course_list first")

        url = f"{NETPULSE_BASE}/np/company/{course.center_id}/class/{course_id}/addExerciser"
        mylogger.debug("\nBooking a course %s", url)
        params = {"exerciserUuid": self._exerciser_uuid}

        resp = await self.session.post(
            url,
            params=params,
            headers=self._np_headers(),
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        body = await resp.text()
        mylogger.debug("status: %s body: %s", resp.status, body)
        if resp.status == 401:
            self._invalidate_session()
        if resp.status >= 300:
            raise RuntimeError(f"Booking course {course_id} failed ({resp.status}): {body[:500]}")

    async def cancel_course(self, booking_id):
        """
        Cancels a course.

        booking_id is the Netpulse class id (Course.booking_id_tac, which for this
        API equals course_id_tac). The club it belongs to is looked up from
        self.bookings, falling back to self.courses.
        """
        booking = next((b for b in self.bookings if b.booking_id_tac == booking_id), None)
        club_uuid = booking.center_id if booking else None
        if club_uuid is None:
            course = next((c for c in self.courses if c.course_id_tac == booking_id), None)
            club_uuid = course.center_id if course else None
        if club_uuid is None:
            raise ValueError(f"Unknown booking_id {booking_id}; call get_bookings first")

        url = f"{NETPULSE_BASE}/np/company/{club_uuid}/class/{booking_id}/removeExerciser"
        mylogger.debug("\nCancelling course %s", url)
        params = {"exerciserUuid": self._exerciser_uuid}

        resp = await self.session.post(
            url,
            params=params,
            headers=self._np_headers(),
            allow_redirects=False,
            ssl=self.ssl_context,
        )
        body = await resp.text()
        mylogger.debug("status: %s body: %s", resp.status, body)
        if resp.status == 401:
            self._invalidate_session()
        if resp.status >= 300:
            raise RuntimeError(f"Cancelling course {booking_id} failed ({resp.status}): {body[:500]}")
