import sys

sys.path.insert(0, 'libs')


class SQLConnection:

    def __init__(self, server):
        self.server = server

    def __enter__(self):
        from .creds import sql_server
        self.db_con_str = sql_server(self.server, 'mydb').con_str

        self.db_con_str.autocommit = True

        return self.db_con_str.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_con_str.close()
