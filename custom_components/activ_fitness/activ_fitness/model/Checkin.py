import datetime

class Checkin:
  def __init__(self,start:datetime.datetime,end:datetime.datetime,duration:str,center:str):
    self.start: datetime.datetime= start
    self.end: datetime.datetime = end
    self.duration: str = duration
    self.center: str = center
  
  def __str__(self):
    # return f"{self.start} {self.end} {self.center}"
    return f"{self.start.strftime('%a %d.%m.%Y')} {self.start.strftime('%H:%M')} - {self.end.strftime('%H:%M')} ({self.duration}) {self.center}"

  def __repr__(self):
    return self.__str__()

  def __iter__(self):
    yield from {
      "start": self.start,
      "end": self.end,
      "duration": self.duration,
      "center": self.center,
    }.items()

  @staticmethod
  def from_table_row(table_row):
    date = table_row[0]
    center = table_row[1]
    start_end = table_row[2]
    duration = table_row[3]
    return Checkin(
      datetime.datetime.strptime(date+' '+start_end[0:5],"%d.%m.%Y %H:%M"),
      datetime.datetime.strptime(date+' '+start_end[8:13],"%d.%m.%Y %H:%M"),
      duration,
      center)

  """ 
['Datum', 'Studio', 'Uhrzeit', 'Dauer']
['29.11.2022', '', '17:31 - 19:14', '01:42']
['24.11.2022', '', '17:49 - 19:44', '01:55']
['21.11.2022', '', '18:10 - 20:06', '01:55']
  """

# date = '29.11.2022'
# start_end = '17:31 - 19:14'

# start = datetime.datetime.strptime(date+' '+start_end[0:5],"%d.%m.%Y %H:%M")
# print(start)