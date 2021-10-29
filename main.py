import sqlite3
import sys
from sqlite3 import ProgrammingError, OperationalError
import requests
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTableWidgetItem
import bcrypt
from main_ui import Ui_MainWindow
from bs4 import BeautifulSoup

API = '86505f1aa3416b810d7460702718476bf11f60a003fddc2b030c92dc98be2397'
LEAGUES_ID = {'АПЛ': '152', 'РПЛ': '344', 'Серия А': '207', 'Ла лига': '302', 'Лига 1': '168', 'Бундеслига': '175'}
COUNTRIES_ID = {'England': '44', 'Spain': '6', 'France': '3', 'Germany': '4', 'Italy': '5', 'Russia': '95'}
COUNTRIES_LEAGUE = {'Russia': 'РПЛ', 'England': 'АПЛ', 'Spain': 'Ла лига', 'France': 'Лига 1', 'Germany': 'Бундеслига',
                    'Italy': 'Серия А'}


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

    def update_data(self, d: dict, params: dict, table: str):
        lst = []
        for k, v in d.items():
            lst.append(f"{k} = '{v}'")
        s = ', '.join(lst)
        arr = list(map(lambda x: f"{x[0]} = '{x[1]}'", params.items()))
        s2 = ' AND '.join(arr)
        q = f"""UPDATE {table} SET {s} WHERE {s2}"""
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
        if s:
            q = f"""SELECT {col} FROM {table} WHERE {s}"""
        else:
            q = f"""SELECT {col} FROM {table}"""
        return self.cur.execute(q).fetchall()

    def close_connection(self):
        self.con.close()


def upload_data():
    try:
        db = DbDispatcher('football_data.db')
        for i in COUNTRIES_ID.values():
            req = requests.get(f'https://apiv3.apifootball.com/?action=get_leagues&country_id={i}&APIkey={API}')
            for dct in req.json():
                if dct['league_id'] in LEAGUES_ID.values():
                    db.write_data({'country_name': dct['country_name'], 'country_logo': dct['country_logo'],
                                   'league_name': dct['league_name'], 'league_logo': dct['league_logo']}, 'leagues')
        for i in LEAGUES_ID.values():
            req = requests.get(f'https://apiv3.apifootball.com/?action=get_teams&league_id={i}&APIkey={API}')
            for dct in req.json():
                players = dct['players']
                team_name = "{}".format(dct['team_name']).replace('\'', '')
                db.write_data({'leag_id': str(i), 'team_name': team_name, 'team_logo': dct['team_badge']},
                              'teams')
                team_id = db.select_data({'team_name': team_name}, 'teams', columns=['id'])[0][0]
                name = "{}".format(dct['coaches'][0]['coach_name']).replace('\'', '')
                db.write_data({'name': name, 'country': dct['coaches'][0]['coach_country'],
                               'age': dct['coaches'][0]['coach_age'],
                               'team_id': team_id},
                              'coaches')
                for player in players:
                    name = "{}".format(player['player_name']).replace('\'', '')
                    db.write_data({'team_id': team_id, 'image': player['player_image'], 'name': name,
                                   'type': player['player_type'], 'age': player['player_age'],
                                   'country': player['player_country'], 'number': player['player_number'],
                                   'goals': player['player_goals'], 'assists': player['player_assists']}, 'players')
        db.close_connection()
    except ProgrammingError as e:
        print('Programming Error')
        print(e)
    except OperationalError as e:
        print('Operational Error')
        print(e)
    except Exception as e:
        print('Unexpected error')
        print(e)


def get_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36'
    }
    req = requests.get(url, headers=headers)
    with open('news.html', 'w', encoding='utf-8') as f:
        f.write(req.text)


def get_events(b_date, e_date, league_id):
    req = requests.get(f'https://apiv3.apifootball.com/?action=get_events&'
                       f'from={b_date}&to={e_date}&league_id={league_id}&APIkey={API}')
    res = []
    for match in req.json():
        d = {'match_id': match['match_id'], 'league_id': match['league_id'], 'league_name': match['league_name'],
             'match_date': match['match_date'], 'match_time': match['match_time'],
             'match_hometeam_name': match['match_hometeam_name'], 'match_awayteam_name': match['match_awayteam_name']}
        res.append(d)
    return res


def get_standings(leag_id):
    req = requests.get(f'https://apiv3.apifootball.com/?action=get_standings&league_id={leag_id}&APIkey={API}')
    res = []
    for dct in req.json():
        temp = [dct['team_name'], dct['overall_league_payed'], dct['overall_league_W'],
                dct['overall_league_D'], dct['overall_league_L'], dct['overall_league_PTS']]
        res.append(temp)
    return res


def get_top_players(leag_id):
    req = requests.get(f'https://apiv3.apifootball.com/?action=get_topscorers&league_id={leag_id}&APIkey={API}')
    res = []
    lst = []
    for dct in req.json():
        temp = [dct['player_name'], dct['goals'], dct['assists']]
        if temp[0] not in lst:
            res.append(temp)
            lst.append(temp[0])
    return res


def parsing_news():
    url = 'https://www.sports.ru/football/news/'
    get_page(url)
    with open('news.html', 'r', encoding='utf-8') as f:
        src = f.read()
    soup = BeautifulSoup(src, 'html.parser')
    news = soup.find_all('a', class_='short-text')
    res = []
    for a in news:
        if a.get('href') and a.get('title'):
            res.append((a.get('title'), a.get('href')))
    return res


# add_url = 'https://www.sports.ru/' (url, который надо прибавлять к res[i][1])


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Application')
        self.save_btn.clicked.connect(self.save_data)
        self.db = DbDispatcher('football_data.db')
        self.teams = self.db.select_data({}, 'teams', ['team_name'])
        self.teams = sorted(list(map(lambda x: x[0], self.teams)))
        self.favClub_comboBox.addItems(self.teams)
        temp = self.db.select_data({}, 'leagues', ['country_name'])
        self.leagues = []
        for country in temp:
            self.leagues.append(COUNTRIES_LEAGUE[country[0]])
        self.comboBox_2.addItems(self.leagues)
        self.comboBox_2.activated[str].connect(self.league_change)
        # данные из формы авторизации
        self.current_login = ''
        self.len_current_passw = 0
        self.current_club = ''
        self.login_lineEdit.setText(self.current_login)
        self.passw_lineEdit.setText('*' * self.len_current_passw)
        self.favClub_comboBox.setCurrentText(self.current_club)
        self.db.close_connection()

    def save_data(self):
        login = self.login_lineEdit.text()
        passw = self.passw_lineEdit.text()
        club = self.favClub_comboBox.currentText()
        msg = QMessageBox(self)
        if login and passw:
            hash = bcrypt.hashpw(passw.encode(), bcrypt.gensalt())
            hash = str(hash).replace('\'', '')
            db = DbDispatcher('profiles.db')
            x = db.select_data({'name': login}, 'users')
            if x:
                if login == self.current_login:
                    db.update_data({'name': login, 'password': hash, 'team_name': club}, {'name': login}, 'users')
            else:
                db.write_data({'name': login, 'password': hash, 'team_name': club}, 'users')
            msg.setIcon(QMessageBox.Information)
            msg.setText('Данные успешно сохранены')
            db.close_connection()

        else:
            msg.setText('Не все поля заполнены')
            msg.setIcon(QMessageBox.Warning)
        msg.setDefaultButton(QMessageBox.Ok)
        msg.show()

    def league_change(self, text):
        leag_id = LEAGUES_ID[text]
        stg = get_standings(leag_id)
        headers = ['Клуб', 'И', 'В', 'Н', 'П', 'О']
        self.tableWidget_4.setRowCount(len(stg))
        self.tableWidget_4.setColumnCount(len(headers))
        self.tableWidget_4.setHorizontalHeaderLabels(headers)
        for i in range(len(stg)):
            for j in range(len(stg[i])):
                self.tableWidget_4.setItem(i, j, QTableWidgetItem(stg[i][j]))
        lst = get_top_players(leag_id)
        assists = list(filter(lambda x: x[-1], lst))
        assists.sort(key=lambda x: int(x[-1]), reverse=True)
        self.tableWidget_3.setRowCount(5)
        self.tableWidget_3.setColumnCount(2)
        self.tableWidget_3.setHorizontalHeaderLabels(['Имя', 'Голы'])
        in_table = []
        for i in range(5):
            for j in range(len(lst[i]) - 1):
                if j == 0:
                    if lst[i][j] not in in_table:
                        self.tableWidget_3.setItem(i, j, QTableWidgetItem(lst[i][j]))
                        in_table.append(lst[i][j])
                    else:
                        continue
                else:
                    self.tableWidget_3.setItem(i, j, QTableWidgetItem(lst[i][j]))
        self.tableWidget_5.setRowCount(len(assists))
        self.tableWidget_5.setColumnCount(2)
        self.tableWidget_5.setHorizontalHeaderLabels(['Имя', 'Ассисты'])
        arr = []
        for item in assists:
            arr.append([item[0], item[2]])
        itr = len(assists) if len(assists) < 5 else 5
        for i in range(itr):
            for j in range(len(arr[i])):
                self.tableWidget_5.setItem(i, j, QTableWidgetItem(arr[i][j]))

    def run(self):
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec_())
