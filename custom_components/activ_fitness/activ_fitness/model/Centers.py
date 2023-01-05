import json
from .Center import Center
from .Course import Course

class Centers:
  def __init__(self,centers,centers_by_id,centers_by_name):
    self.centers:list[Center] = centers
    self.centers_by_id:dict = centers_by_id
    self.centers_by_name:dict = centers_by_name

  @staticmethod
  def from_json_str(json_str):
    content_json = json.loads(json_str)
    centers_lst = []
    for c in content_json:
      if (c['title']=='Activ Fitness'):
        centers_lst = c['centers']

    centers_obj_lst = []
    for c in centers_lst:
      centers_obj_lst.append(Center.from_json(c))

    centers_by_id = {c.center_id:c.title for c in centers_obj_lst}    
    centers_by_name = {c.title:c.center_id for c in centers_obj_lst}   

    return Centers(centers_obj_lst,centers_by_id,centers_by_name)
