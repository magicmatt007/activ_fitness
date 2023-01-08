from html.parser import HTMLParser


class MyHTMLParser(HTMLParser):
    """MyHTMLParser class."""

    def __init__(self, decode_html_entities: bool = False, data_separator: str = " "):
        HTMLParser.__init__(self, convert_charrefs=decode_html_entities)

        self._data_separator = data_separator

        self._in_cell = False  # table cell
        self._in_row = False  # table row
        self._in_row_divider = False  # table row
        self._in_table = False  # table
        self._current_table = []
        self._current_row = []
        self._current_cell = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        div_class = [a[1] for a in attrs if a[0] == "class"]
        div_class_ext = []
        for d in div_class:
            div_class_ext.extend(d.split())
        if "table" in div_class_ext:  # cell
            self._in_table = True

        if "table-cell" in div_class_ext:  # cell
            self._in_cell = True
        if "table-row" in div_class_ext:  # cell
            self._in_row = True
            if "divider" in div_class_ext:
                self._in_row_divider = True

    def handle_endtag(self, tag):
        if self._in_cell:
            self._in_cell = False
            final_cell = self._data_separator.join(self._current_cell).strip()
            self._current_row.append(final_cell)
            self._current_cell = []
        elif self._in_row:
            self._in_row = False
            if not self._in_row_divider:
                self._current_table.append(self._current_row)
            self._current_row = []
            if self._in_row_divider:
                self._in_row_divider = False
        elif self._in_table:
            self._in_table = False
            self.tables.append(self._current_table)

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data.strip())
