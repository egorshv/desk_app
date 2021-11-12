import sqlite3
import sys
from sqlite3 import ProgrammingError, OperationalError
import requests
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTableWidgetItem, QDialog
from datetime import datetime

from pyqt5_plugins.examplebutton import QtWidgets

from form_ui import Ui_Form
from main_ui import Ui_MainWindow
from bs4 import BeautifulSoup

API = '34b92796e758d54d2ba955051b81e9daa014d897dc90f601b82b81bb27e3385c'
LEAGUES_ID = {'АПЛ': '152', 'РПЛ': '344', 'Серия А': '207', 'Ла лига': '302', 'Лига 1': '168', 'Бундеслига': '175'}
COUNTRIES_ID = {'England': '44', 'Spain': '6', 'France': '3', 'Germany': '4', 'Italy': '5', 'Russia': '95'}
COUNTRIES_LEAGUE = {'Russia': 'РПЛ', 'England': 'АПЛ', 'Spain': 'Ла лига', 'France': 'Лига 1', 'Germany': 'Бундеслига',
                    'Italy': 'Серия А'}
TEAMS = ''
TEXTS = []
CURRENT_USER_ID = 0
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36'
}


class DbDispatcher:
    def __init__(self, filename):
        self.filename = filename
        self.con = sqlite3.connect(filename)
        self.cur = self.con.cursor()

    def write_data(self, d: dict, table: str):
        # d: key - столбец, value - значение
        lst2 = []
        for i in d.values():
            lst2.append(f'\'{i}\'')
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

    def get_max_id(self, table):
        q = f"""SELECT MAX(id) FROM {table}"""
        return self.cur.execute(q).fetchone()

    def close_connection(self):
        self.con.close()


def get_text():
    news = parsing_news()
    for n in news:
        db = DbDispatcher('news.db')
        db.write_data({'title': n[0]}, 'news')
        db.close_connection()


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
    except ProgrammingError as er:
        print('Programming Error')
        print(er)
    except OperationalError as er:
        print('Operational Error')
        print(er)
    except Exception as er:
        print('Unexpected error')
        print(er)


def get_page(url):
    req = requests.get(url, headers=headers)
    with open('news.html', 'w', encoding='utf-8') as f:
        text = req.text
        f.write(text)


def get_events(b_date, e_date, league_id):
    req = requests.get(f'https://apiv3.apifootball.com/?action=get_events&'
                       f'from={b_date}&to={e_date}&league_id={league_id}&APIkey={API}')
    res = []
    try:
        if 'error' in req.json().keys():
            return []
    except AttributeError:
        for match in req.json():
            d = {'match_id': match['match_id'], 'league_id': match['league_id'],
                 'league_name': match['league_name'], 'match_date': match['match_date'],
                 'match_time': match['match_time'], 'match_hometeam_name': match['match_hometeam_name'],
                 'match_awayteam_name': match['match_awayteam_name']}
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

class CustomDialog(QDialog, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Form")
        self.setupUi(self)
        self.pushButton.clicked.connect(self.enter)
        self.pushButton_2.clicked.connect(self.discard)
        self.comboBox.addItems(TEAMS)

    def enter(self):
        global CURRENT_USER_ID
        db = DbDispatcher('profiles.db')
        user_names = db.select_data({}, 'users', ['id', 'name', 'password'])
        login = self.lineEdit.text()
        club = self.comboBox.currentText()
        flag = True
        passw = self.lineEdit_2.text()
        if login and passw:
            for i in user_names:
                if login in i:
                    if passw == i[2]:
                        CURRENT_USER_ID = i[0]
                        self.close()
                        flag = False
                        break
                    else:
                        msg_ = QMessageBox(self)
                        msg_.setIcon(QMessageBox.Warning)
                        msg_.setWindowTitle('Ошибка')
                        msg_.setText('Проверьте корректность данных')
                        msg_.setDefaultButton(QMessageBox.Ok)
                        flag = False
                        msg_.show()
                        break
            if flag:
                db.write_data({'name': login, 'password': passw, 'team_name': club}, 'users')
                CURRENT_USER_ID = int(db.get_max_id('users')[0])
                self.close()
        else:
            msg2 = QMessageBox(self)
            msg2.setIcon(QMessageBox.Warning)
            msg2.setWindowTitle('Ошибка')
            msg2.setText('Не все поля заполнены')
            msg2.setDefaultButton(QMessageBox.Ok)
            msg2.show()

    @staticmethod
    def discard():
        quit()


def write_matches(table, lst):
    if lst:
        table.setRowCount(len(lst))
        table.setColumnCount(4)
        table.setShowGrid(False)
        table.setColumnWidth(0, 15)
        table.setColumnWidth(2, 2)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        for i in range(len(lst)):
            tmp = [lst[i]['match_time'], lst[i]['match_hometeam_name'], ':',
                   lst[i]['match_awayteam_name']]
            for j in range(4):
                elem = QTableWidgetItem(tmp[j])
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                table.setItem(i, j, elem)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        global TEAMS
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Здесь могла быть ваша реклама')
        self.save_btn.clicked.connect(self.save_data)
        self.db = DbDispatcher('football_data.db')
        self.db_prof = DbDispatcher('profiles.db')
        self.teams = self.db.select_data({}, 'teams', ['team_name'])
        self.teams = list(map(lambda x: x[0], self.teams))
        self.teams.sort()
        self.favClub_comboBox.addItems(self.teams)
        TEAMS = self.teams
        temp = self.db.select_data({}, 'leagues', ['country_name'])
        self.leagues = []
        for country in temp:
            self.leagues.append(COUNTRIES_LEAGUE[country[0]])
        self.comboBox_2.addItems(self.leagues)
        self.comboBox_2.activated[str].connect(self.league_change)
        # данные из формы авторизации
        self.dlg = CustomDialog()
        self.dlg.setStyleSheet(open('style.css').read())
        self.dlg.setModal(True)
        self.dlg.show()
        self.dlg.exec()
        user_data = self.db_prof.select_data({'id': CURRENT_USER_ID}, 'users', ['name', 'password', 'team_name'])[0]
        self.current_login = user_data[0]
        self.current_passw = user_data[1]
        self.current_club = user_data[2]
        self.login_lineEdit.setText(self.current_login)
        self.passw_lineEdit.setText(self.current_passw)
        self.favClub_comboBox.setCurrentText(self.current_club)
        self.news()
        self.matches()
        self.my_club()

    def save_data(self):
        login = self.login_lineEdit.text()
        passw = self.passw_lineEdit.text()
        club = self.favClub_comboBox.currentText()
        msg_ = QMessageBox(self)
        if login and passw:
            db = DbDispatcher('profiles.db')
            x = db.select_data({'name': login}, 'users')
            if x:
                if login == self.current_login:
                    db.update_data({'name': login, 'password': passw, 'team_name': club}, {'name': login}, 'users')
            else:
                db.write_data({'name': login, 'password': passw, 'team_name': club}, 'users')
            msg_.setIcon(QMessageBox.Information)
            msg_.setText('Данные успешно сохранены')
            db.close_connection()

        else:
            msg.setText('Не все поля заполнены')
            msg.setIcon(QMessageBox.Warning)
        msg.setDefaultButton(QMessageBox.Ok)
        msg.show()

    def my_club(self):
        db = DbDispatcher('football_data.db')
        leag_id = db.select_data({'team_name': self.current_club}, 'teams', ['leag_id'])[0][0]
        stg = get_standings(leag_id)
        _headers = ['Клуб', 'И', 'В', 'Н', 'П', 'О']
        self.tableWidget.setRowCount(len(stg))
        self.tableWidget.setColumnCount(len(_headers))
        self.tableWidget.setHorizontalHeaderLabels(_headers)
        self.tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i in range(1, 6):
            self.tableWidget.setColumnWidth(i, 15)
        for i in range(len(stg)):
            for j in range(len(stg[i])):
                elem = QTableWidgetItem(stg[i][j])
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget.setItem(i, j, elem)
        _id = db.select_data({'team_name': self.current_club}, 'teams', ['id'])[0][0]
        players = db.select_data({'team_id': _id}, 'players', ['name', 'type', 'number'])
        headers2 = ['Имя', 'Позиция', 'Номер']
        self.tableWidget_2.setRowCount(len(players))
        self.tableWidget_2.setColumnCount(len(headers2))
        self.tableWidget_2.setHorizontalHeaderLabels(headers2)
        self.tableWidget_2.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i in range(len(players)):
            for j in range(len(players[i])):
                elem = QTableWidgetItem(str(players[i][j]))
                elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget_2.setItem(i, j, elem)
        gls = db.select_data({'team_id': _id}, 'players', ['name', 'goals'])
        gls.sort(key=lambda x: int(x[-1]))
        gls.reverse()
        gls = gls[:5]
        assists = db.select_data({'team_id': _id}, 'players', ['name', 'assists'])
        assists.sort(key=lambda x: int(x[-1]))
        assists.reverse()
        assists = assists[:5]
        headers3 = ['Имя', 'Голы']
        self.tableWidget_6.setRowCount(len(gls))
        self.tableWidget_6.setColumnCount(len(headers3))
        self.tableWidget_6.setHorizontalHeaderLabels(headers3)
        self.tableWidget_6.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i in range(len(gls)):
            for j in range(len(headers3)):
                elem = QTableWidgetItem(str(gls[i][j]))
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget_6.setItem(i, j, elem)
        headers4 = ['Имя', 'Ассисты']
        self.tableWidget_7.setRowCount(len(assists))
        self.tableWidget_7.setColumnCount(len(headers4))
        self.tableWidget_7.setHorizontalHeaderLabels(headers4)
        self.tableWidget_7.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i in range(len(assists)):
            for j in range(len(headers4)):
                elem = QTableWidgetItem(str(assists[i][j]))
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget_7.setItem(i, j, elem)

    def league_change(self, text):
        leag_id = LEAGUES_ID[text]
        stg = get_standings(leag_id)
        headers_ = ['Клуб', 'И', 'В', 'Н', 'П', 'О']
        self.tableWidget_4.setRowCount(len(stg))
        self.tableWidget_4.setColumnCount(len(headers_))
        self.tableWidget_4.setHorizontalHeaderLabels(headers_)
        self.tableWidget_4.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i in range(1, 6):
            self.tableWidget_4.setColumnWidth(i, 15)
        for i in range(len(stg)):
            for j in range(len(stg[i])):
                elem = QTableWidgetItem(stg[i][j])
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget_4.setItem(i, j, elem)
        lst = get_top_players(leag_id)
        assists = list(filter(lambda x: x[-1], lst))
        assists.sort(key=lambda x: int(x[-1]))
        assists.reverse()
        self.tableWidget_3.setRowCount(5)
        self.tableWidget_3.setColumnCount(2)
        self.tableWidget_3.setHorizontalHeaderLabels(['Имя', 'Голы'])
        self.tableWidget_3.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        in_table = []
        for i in range(5):
            for j in range(len(lst[i]) - 1):
                elem = QTableWidgetItem(lst[i][j])
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                if j == 0:
                    if lst[i][j] not in in_table:
                        self.tableWidget_3.setItem(i, j, elem)
                        in_table.append(lst[i][j])
                    else:
                        continue
                else:
                    self.tableWidget_3.setItem(i, j, elem)
        self.tableWidget_5.setRowCount(len(assists))
        self.tableWidget_5.setColumnCount(2)
        self.tableWidget_5.setHorizontalHeaderLabels(['Имя', 'Ассисты'])
        self.tableWidget_5.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        arr = []
        for item in assists:
            arr.append([item[0], item[2]])
        if len(assists) < 5:
            itr = len(assists)
        else:
            itr = 5
        for i in range(itr):
            for j in range(len(arr[i])):
                elem = QTableWidgetItem(arr[i][j])
                if j != 0:
                    elem.setTextAlignment(Qt.AlignHCenter)
                self.tableWidget_5.setItem(i, j, elem)

    def news(self):
        db = DbDispatcher('news.db')
        news = db.select_data({}, 'news', ['title'])
        news = list(map(lambda x: str(news.index(x) + 1) + '. ' + x[0] + '\n', news))
        self.listWidget.addItems(news)

    def matches(self):
        date = datetime.today().strftime('%Y-%m-%d')
        # date = '2021-11-20'
        epl_matches = get_events(date, date, 152)
        rpl_matches = get_events(date, date, 344)
        seria_a_matches = get_events(date, date, 207)
        la_liga_matches = get_events(date, date, 302)
        ligue_1_matches = get_events(date, date, 168)
        bundesliga_matches = get_events(date, date, 175)
        if epl_matches:
            write_matches(self.tableWidget_8, epl_matches)
        else:
            self.tableWidget_8.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))
        if rpl_matches:
            write_matches(self.tableWidget_9, rpl_matches)
        else:
            self.tableWidget_9.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))
        if seria_a_matches:
            write_matches(self.tableWidget_13, seria_a_matches)
        else:
            self.tableWidget_13.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))
        if la_liga_matches:
            write_matches(self.tableWidget_10, la_liga_matches)
        else:
            self.tableWidget_10.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))
        if ligue_1_matches:
            write_matches(self.tableWidget_12, ligue_1_matches)
        else:
            self.tableWidget_12.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))
        if bundesliga_matches:
            write_matches(self.tableWidget_11, bundesliga_matches)
        else:
            self.tableWidget_11.setItem(0, 0, QTableWidgetItem('Сегодня матчей нет'))


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        form = MainWindow()
        form.setStyleSheet(open('style.css').read())
        form.show()
        sys.exit(app.exec_())
    except Exception as e:
        msg = QMessageBox()
        msg.setWindowTitle('Ошибка')
        msg.setText(str(e))
        msg.setDefaultButton(QMessageBox.Ok)
        msg.setIcon(QMessageBox.Warning)
        msg.show()
        msg.exec()
