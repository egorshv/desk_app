import sqlite3
from sqlite3 import ProgrammingError, OperationalError
import requests
from bs4 import BeautifulSoup

API = '86505f1aa3416b810d7460702718476bf11f60a003fddc2b030c92dc98be2397'
LEAGUES_ID = {'EPL': '152', 'RPL': '344', 'Serie A': '207', 'La Liga': '302', 'Ligue 1': '168', 'Bundesliga': '175'}
COUNTRIES_ID = {'England': '44', 'Spain': '6', 'France': '3', 'Germany': '4', 'Italy': '5', 'Russia': '95'}


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
