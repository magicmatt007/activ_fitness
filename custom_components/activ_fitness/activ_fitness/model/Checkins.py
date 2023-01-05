from .Checkin import Checkin

class Checkins:
  def __init__(self,checkins):
    self.checkins:list[Checkin] = checkins

  @property
  def checkins_in_period(self):
    return len(self.checkins)

  @property
  def visits_per_month(self):
    month_lst = [0] *13
    for c in self.checkins:
      month_lst[c.start.month] +=1 
    print(month_lst)
    return month_lst

  @property
  def visits_per_week(self):
    week_lst = [0] *54
    for c in self.checkins:
      week_lst[c.start.isocalendar().week] +=1 
    print(week_lst)
    return week_lst

  @property
  def last_checkin(self): 
    if len(self.checkins) == 0:
      return None
    last_checkin_date = self.checkins[0].start
    for c in self.checkins:
      if c.start > last_checkin_date:
        last_checkin_date = c.start
    return last_checkin_date 


  @staticmethod
  def from_table(table):
    # print(f"\nVisits between {from_} and {to_}: {len(t)-1}")
    checkins_obj_lst = []
    for r in table[1:]:
      checkins_obj_lst.append(Checkin.from_table_row(r))

    return Checkins(checkins_obj_lst)
