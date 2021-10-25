import sqlite3
from sqlite3 import ProgrammingError, OperationalError


class UploadData:
    pass


class DbDispatcher:
    def __init__(self, filename):
        self.filename = filename
        self.con = sqlite3.connect(filename)
        self.cur = self.con.cursor()

    def write_data(self, d: dict, table: str):
        # d: key - столбец, value - значение
        lst2 = [f'\'{i}\'' for i in d.values()]
        s1 = ', '.join(d.keys())
        s2 = ', '.join(lst2)
        assert len(d.keys()) == len(d.values())
        q = f"""INSERT INTO {table} ({s1}) VALUES ({s2})"""
        self.cur.execute(q)
        self.con.commit()

    def read_all_data(self, table: str):
        q = f"""SELECT * FROM {table}"""
        return self.cur.execute(q).fetchall()

    def select_data(self, d: dict, table: str, columns=None):
        # d - параметры поиска
        # table - таблица, в которой надо искать
        # columns - столбцы, которые надо вывести
        lst = []
        for item in d.items():
            try:
                lst.append(f'{item[0]}={int(item[1])}')
            except ValueError:
                lst.append(f"{item[0]}='{item[1]}'")
        s = ' AND '.join(lst)
        if columns:
            col = ', '.join(columns)
        else:
            col = '*'
        q = f"""SELECT {col} FROM {table} WHERE {s}"""
        return self.cur.execute(q).fetchall()

    def close_connection(self):
        self.con.close()
