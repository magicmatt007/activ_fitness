import asyncio
import aiohttp
import ssl
import certifi

import my_secrets

from activ_fitness import api


#####################################################
# Playground to try API interactions:

async def main():
  session = aiohttp.ClientSession()
  ssl_context = ssl.create_default_context(cafile=certifi.where()) # to ensure it runs independent of local machine's CA store

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
        courselist = await api.get_course_list(session=session,ssl_context=ssl_context,coursetitle="",centerIds=[23,33,54])
        for c in sorted(courselist.courses_set):
          print(c)
      case "2":
        center_ids = await api.get_center_ids(session=session,ssl_context=ssl_context)
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
        courselist = await api.get_course_list(session=session,ssl_context=ssl_context,coursetitle="BODYPUMP® 55'",centerIds=[23,33,54])
        # courselist = get_course_list(coursetitle="",centerIds=[144,34])
        for c in courselist.courses:
          print(c)
        print(courselist.centers)
      case "4":
        access_token = await api.login(session=session,ssl_context=ssl_context,user=my_secrets.user,pwd=my_secrets.pwd)
        bookings = await api.get_bookings(session=session,ssl_context=ssl_context, access_token=access_token)
        print(bookings.courses)
      case "5":
        #### Book a course example workflow:
        access_token =await api.login(session=session,ssl_context=ssl_context,user=my_secrets.user,pwd=my_secrets.pwd) # requires a login

        print("Book a course:")
        courselist = await api.get_course_list(session=session,ssl_context=ssl_context,coursetitle="BODYPUMP® 55'")
        for index,c in enumerate(courselist.courses_bookable):
          print(index,c)

        select = input('Which course do you want to book? ')

        # api.book_course(access_token=access_token,course_id=courselist.courses_bookable[int(select)].course_id_tac)
        try:
            print('1')
            await api.book_course(session=session,ssl_context=ssl_context,access_token=access_token,course_id=courselist.courses_bookable[int(select)].course_id_tac)
            print('2')
            bookings = await api.get_bookings(session=session,ssl_context=ssl_context,access_token=access_token)
            print('3')
            print(bookings.courses)
            print('4')
        except Exception as e:
            print(f"Invalid selection {e} {e.with_traceback}")
      case "6":
          #### Cancel a course example workflow:
          access_token = await api.login(session=session,ssl_context=ssl_context,user=my_secrets.user,pwd=my_secrets.pwd) # requires a login:

          print("Cancel a course:")
          bookings = await api.get_bookings(session=session,ssl_context=ssl_context, access_token=access_token)

          for index,b in enumerate(bookings.courses):
            print(index,b)

          select = input('Which course do you want to cancel? ')

          try:
            await api.cancel_course(session=session,ssl_context=ssl_context, access_token=access_token,booking_id=bookings.courses[int(select)].booking_id_tac)
            bookings = await api.get_bookings(session=session,ssl_context=ssl_context, access_token=access_token)
            print(bookings.courses)
          except:
            print("Invalid selection")
      case "7":
        access_token = await api.login(session=session,ssl_context=ssl_context,user=my_secrets.user,pwd=my_secrets.pwd) # requires a login
        from_ = "2020-01-01"
        to_ = "2022-12-31"

        checkins = await api.get_checkins(session=session,ssl_context=ssl_context,from_=  from_ ,to_=  to_)
        print(f"\nVisits between {from_} and {to_}: {checkins.visits_in_period()}")
        print(f"Last Checkin: {checkins.last_visit()}")
        # print(checkins.checkins)
        for c in checkins.checkins:
          print(c)
        # checkins.visits_per_month()
        # checkins.visits_per_week()
      case "x":
        break
      case _:
        print("Invalid selection")

if __name__ == "__main__":
  asyncio.run(main())
