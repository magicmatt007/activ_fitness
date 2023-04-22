import asyncio
import logging
import ssl

from activ_fitness.api_class import Api
import aiohttp
import certifi
import my_secrets

#####################################################
# Playground to try API interactions:


# logging.basicConfig(level=logging.DEBUG)
# logging.debug("This will get logged")

logger = logging.getLogger("mylogger")
logger.setLevel(logging.DEBUG)


async def main():
    """Main."""
    session = aiohttp.ClientSession()
    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )  # to ensure it runs independent of local machine's CA store

    _api = Api(session=session, ssl_context=ssl_context)

    while True:
        print("Select:")
        print("1: List available courses in given centers")
        print("2: List Center IDs")
        print("3: List upcoming course schedule in given centers")
        print("4: List bookings")
        print("5: Book a course")
        print("6: Cancel a course")
        print("7: List checkins")
        print("8: Test Api object")
        print("x: Exit")
        selection = input("Your choice: ")

        match selection:
            case "1":
                courselist = await _api.get_course_list(
                    coursetitles=[""], center_ids=[23, 33, 54]
                )
                for c in sorted(courselist.coursetitles):
                    print(c)
            case "2":
                center_ids = await _api.get_center_ids()
                print(f"_api.centers: {_api.centers}")
                # print(center_ids.centers_by_id)
                for c in center_ids.centers_by_id:
                    print(str(c).rjust(3), center_ids.centers_by_id[c])
                selection = input("Enter centers separated by commas: ")
                try:
                    selected_centers = [int(id) for id in selection.split(",")]
                    print(selected_centers)
                except:
                    print("Invalid selection")
            case "3":
                access_token = await _api.login(
                    user=my_secrets.user, pwd=my_secrets.pwd
                )
                courselist = await _api.get_course_list(
                    coursetitles=["BODYPUMP® 55'"], center_ids=[23, 33, 54]
                )
                # courselist = get_course_list(coursetitle="",centerIds=[144,34])
                for c in courselist.courses:
                    print(c)
            case "4":
                access_token = await _api.login(
                    user=my_secrets.user, pwd=my_secrets.pwd
                )
                bookings = await _api.get_bookings()
                print(bookings.courses)
            case "5":
                #### Book a course example workflow:
                access_token = await _api.login(
                    user=my_secrets.user, pwd=my_secrets.pwd
                )  # requires a login

                print("Book a course:")
                # courselist = await _api.get_course_list(coursetitles=["BODYPUMP® 55'"])
                courselist = await _api.get_course_list(
                    center_ids=[33, 23, 54], coursetitles=["BODYPUMP® 55'"]
                )
                for index, c in enumerate(courselist.courses_bookable):
                    print(index, c)

                select = input("Which course do you want to book? ")

                # api.book_course(access_token=access_token,course_id=courselist.courses_bookable[int(select)].course_id_tac)
                try:
                    print("1")
                    await _api.book_course(
                        # access_token=access_token,
                        course_id=courselist.courses_bookable[
                            int(select)
                        ].course_id_tac,
                    )
                    print("2")
                    bookings = await _api.get_bookings()
                    print("3")
                    print(bookings.courses)
                    print("4")
                except Exception as e:
                    print(f"Invalid selection {e} {e.with_traceback}")
            case "6":
                #### Cancel a course example workflow:
                access_token = await _api.login(
                    user=my_secrets.user, pwd=my_secrets.pwd
                )  # requires a login:

                print("Cancel a course:")
                bookings = await _api.get_bookings()

                for index, b in enumerate(bookings.courses):
                    print(index, b)

                select = input("Which course do you want to cancel? ")

                try:
                    await _api.cancel_course(
                        booking_id=bookings.courses[int(select)].booking_id_tac
                    )
                    bookings = await _api.get_bookings()
                    print(bookings.courses)
                except:
                    print("Invalid selection")
            case "7":
                access_token = await _api.login(
                    user=my_secrets.user, pwd=my_secrets.pwd
                )  # requires a login
                from_ = "2020-01-01"
                to_ = "2022-12-31"

                checkins = await _api.get_checkins(from_=from_, to_=to_)

                print(f"\nVisits between {from_} and {to_}: {_api.checkins_in_period}")
                print(f"Last Checkin: {_api.last_checkin}")
                # print(checkins.checkins)
                for c in checkins.checkins:
                    print(c)
                # checkins.visits_per_month()
                # checkins.visits_per_week()
            case "8":
                await _api.login(user=my_secrets.user, pwd=my_secrets.pwd)
                await _api.get_center_ids()
                await _api.get_course_list()
                await _api.get_bookings()
                await _api.get_checkins()

                print("\nCenters:")
                for c in _api.centers_by_id:
                    print(str(c).rjust(3), _api.centers_by_id[c])
                selection = input("Enter centers separated by commas: ")
                selected_centers = []
                try:
                    selected_centers = [int(id) for id in selection.split(",")]
                    print(selected_centers)
                    await _api.get_course_list(center_ids=selected_centers)
                except:
                    print("Invalid selection")
                    pass

                print("\nCourses - coursetitles:")
                coursetitles_sorted = sorted(_api.coursetitles)
                print(coursetitles_sorted)
                for index, c in enumerate(coursetitles_sorted):
                    print(str(index).rjust(3), c)
                selection = input("Enter courses separated by commas: ")
                try:
                    selected_courses = [int(id) for id in selection.split(",")]
                    print(selected_courses)
                    selected_course_names = [
                        coursetitles_sorted[i] for i in selected_courses
                    ]
                    print(selected_course_names)
                    # This would be the regular home assistant call to update the (10) course devices:
                    await _api.get_course_list(
                        coursetitles=selected_course_names,
                        center_ids=selected_centers,
                        take=30,
                    )
                except:
                    print("Invalid selection")
                    pass

                print("\nCourses - objects")
                for index, c in enumerate(_api.courses):
                    print(index, c)

                print("\nBookings:")
                print(_api.bookings)
                print("\nCheckins:")
                print(_api.checkins)

            case "x":
                break
            case _:
                print("Invalid selection")


if __name__ == "__main__":
    asyncio.run(main())
