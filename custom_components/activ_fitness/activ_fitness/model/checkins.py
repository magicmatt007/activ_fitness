"""Checkins class."""

from .checkin_x import Checkin


class Checkins:
    """Checkins class."""

    def __init__(self, checkins):
        self.checkins: list[Checkin] = checkins

    @property
    def checkins_in_period(self):
        """Property checkins in period."""
        return len(self.checkins)

    @property
    def visits_per_month(self):
        """Property visits per each month in form of a list."""
        month_lst = [0] * 13
        for checkin in self.checkins:
            month_lst[checkin.start.month] += 1
        print(month_lst)
        return month_lst

    @property
    def visits_per_week(self):
        """Property visits per each week in form of a list."""
        week_lst = [0] * 54
        for checkin in self.checkins:
            week_lst[checkin.start.isocalendar().week] += 1
        print(week_lst)
        return week_lst

    @property
    def last_checkin(self):
        """Property last checkin date."""
        if len(self.checkins) == 0:
            return None
        last_checkin_date = self.checkins[0].start
        for checkin in self.checkins:
            if checkin.start > last_checkin_date:
                last_checkin_date = checkin.start
        return last_checkin_date

    @staticmethod
    def from_table(table):
        """Create instance from table."""
        # print(f"\nVisits between {from_} and {to_}: {len(t)-1}")
        checkins_obj_lst = []
        for row in table[1:]:
            checkins_obj_lst.append(Checkin.from_table_row(row))

        return Checkins(checkins_obj_lst)
