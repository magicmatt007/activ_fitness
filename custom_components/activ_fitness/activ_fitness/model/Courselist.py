import json
from .Center import Center
from .Checkin import Checkin
from .Course import Course

class Courselist:
  def __init__(self,courses):
    self.courses:list[Course] = courses

  @property
  def coursetitles(self):
    return {c.title for c in self.courses}

  @property
  def courses_bookable(self):
    return [c for c in self.courses if c.bookable== True]

  @staticmethod
  def from_json_str(json_str):
    content_dct = json.loads(json_str)
    courses_lst = content_dct['courses']

    courses_obj_lst = []
    for c in courses_lst:
      courses_obj_lst.append(Course.from_json(c))

    return Courselist(courses_obj_lst)

