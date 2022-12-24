from flask import Flask, request
import requests
import json
from dotenv import load_dotenv
import os
from os.path import join, dirname
from pymongo import MongoClient
from waitress import serve

app = Flask(__name__)


def get_from_env(key):   # For work with .env
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    return os.environ.get(key)


def sort_by_key(lst):    # Sort anime dataset by score
    try:
        tmp = lst['score']   # Not every data in table have score, so we use try
    except:
        tmp = 0.0
    return tmp


mc = MongoClient(get_from_env("MONGO_CONNECT"))   # Connect to mongoDB
db = mc['anime']
coll = db['data']
arr = list(coll.find())
arr = sorted(arr, key=sort_by_key)   # Sort data by score
arr.reverse()


def send_message(chat_id, text, name):
    local_coll = db[str(chat_id)]
    if local_coll.find_one({'saw': {"$gt": -1}}) is None:   # Check for first attempt
        access = 0
    elif len(list(local_coll.find_one({'saw': {"$gt": -1}}))) == 0:
        access = 0
    else:                                                               # take access from first data in dataset
        access = local_coll.find_one({'saw': {"$gt": -1}})['command']   # take access for commands

    if text == "Только лучшее" and (access == 0):
        if str(chat_id) in db.list_collection_names():  # check if we've seen title
            local_coll = db[str(chat_id)]
            tmp = local_coll.find_one({'saw': {"$gt": -1}})['saw'] + 1
            while arr[tmp]['uid'] in local_coll.find_one({'saw': {"$gt": -1}})['lst_saw']:
                tmp += 1
            tmp_arr = local_coll.find_one({'saw': {"$gt": -1}})['lst_saw']
            tmp_arr.append(arr[tmp]['uid'])
            local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'saw': tmp, 'lst_saw': tmp_arr}})
        else:
            lst_chat.append(chat_id)
            local_coll = db[str(chat_id)]
            local_coll.insert_one({'saw': 1, "lst_saw": [], "command": 0, "user_name": name})  # create new data
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 1}})
        out = arr[db[str(chat_id)].find_one({'saw': {"$gt": -1}})['saw']]['link']

    elif text == "/start" and (access == 0):
        out = "Этот бот будет предлгать самые лучшие тайтлы, нажимай кнопку 'Только лучшее', чтобы увидеть их. " \
              "Также можно" \
              " отмечать понравившиеся аниме, чтобы было всегда к чему вернуться."

    elif text == "Bruh, man..." and (access == 1):
        out = "Посмотрим ещё"
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})

    elif text == "Not bad" and (access == 1):
        out = "Добавлено в список понравившегося"
        local_coll = db[str(chat_id)]
        tmp = local_coll.find_one({'saw': {"$gt": -1}})['saw']
        local_coll.insert_one({'name': arr[tmp]['title'], 'image': arr[tmp]['img_url']})  # add anime to dataset
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})

    elif text == "Список понравившегося" and (access == 0):
        local_coll = db[str(chat_id)]
        lst = []
        cnt = 0
        if len(list(local_coll.find({'name': {"$gt": ""}}))) == 0:
            out = "НИЧЕГО, ТЕБЕ НИЧЕГО НЕ НРАВИТСЯ"
        else:
            for i in local_coll.find({'name': {"$gt": ""}}):   # iterate by liked titles
                cnt += 1
                lst.append(str(cnt))
                lst.append(") ")
                lst.append(i['name'])
                lst.append('\n')
            out = ''.join(lst)
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 2}})

    elif text == "Что-то разонравилось или надоело" and (access == 2):
        out = "Введи номер из списка"
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 3}})

    elif text == "Ой, случайно не добавил тайтл" and (access == 2):
        out = "Введи название тайтла"
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 4}})

    elif text.isnumeric() and (access == 3):
        local_coll = db[str(chat_id)]
        if local_coll.find({'name': {"$gt": ""}}) is None:
            out = "Как удалить то, чего нет???"
        else:
            max_cnt = len(list(local_coll.find({'name': {"$gt": ""}})))
            cnt = int(text)
            if cnt > max_cnt or cnt <= 0:
                out = "Как удалить то, чего нет???"
            else:
                check = 0
                for i in local_coll.find({'name': {"$gt": ""}}):    # we need to iterate, because we don't remember
                    check += 1                                      # numbers of list
                    if check == cnt:
                        local_coll.delete_one({"name": i["name"]})
                        break
                out = "Удалено"
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})

    elif text == "Посмотрел на свой список, всё норм" and (access == 2):
        out = "Перейдем к дальнейшему просмотру"
        local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})

    else:
        out = "Какая-то ошибка"
        if access != 4:                  # problems with access, mean we used wrong command
            out = "Кажется ввели что-то не то, давайте вернёмся к началу"
            text = "Back to the roots"
            local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})
        else:
            if coll.find_one({'title': text}) is None:    # can't find title
                out = "Кажется ввели что-то не то"
            else:
                tmp = coll.find_one({'title': text})
                local_coll = db[str(chat_id)]
                local_coll.insert_one({'name': tmp['title'], 'image': tmp['img_url']})
                out = "Добавлен новый тайтл"
            local_coll.update_one({'saw': {"$gt": -1}}, {'$set': {'command': 0}})

    method = "sendMessage"
    token = get_from_env("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"    # create url

    if text == "Только лучшее":                            # return data with text and buttons
        data = {"chat_id": chat_id, "text": out, "reply_markup": json.dumps({"keyboard": [[{"text": "Not bad"}],
                                                                                          [{
                                                                                              "text": "Bruh, man..."}]],
                                                                             "resize_keyboard": True,
                                                                             "one_time_keyboard": True})}

    elif text == "Список понравившегося":
        data = {"chat_id": chat_id, "text": out, "reply_markup": json.dumps({"keyboard": [[{"text": "Что-то "
                                                                                                    "разонравилось "
                                                                                                    "или надоело"}],
                                                                                          [{
                                                                                              "text": "Ой, случайно "
                                                                                                      "не добавил "
                                                                                                      "тайтл"}],
                                                                                          [{
                                                                                              "text": "Посмотрел на "
                                                                                                      "свой список, "
                                                                                                      "всё норм"}]
                                                                                          ],
                                                                             "resize_keyboard": True,
                                                                             "one_time_keyboard": True})}

    elif text == "Что-то разонравилось или надоело":
        data = {"chat_id": chat_id, "text": out}

    elif text == "Ой, случайно не добавил тайтл":
        data = {"chat_id": chat_id, "text": out}

    else:
        data = {"chat_id": chat_id, "text": out, "reply_markup": json.dumps({"keyboard": [[{"text": "Только лучшее"}],
                                                                                          [{
                                                                                              "text": "Список "
                                                                                                      "понравившегося"}]],
                                                                             "resize_keyboard": True,
                                                                             "one_time_keyboard": True})}
    requests.post(url, data=data)


i_glob = 0


def cnt():
    global i_glob
    i_glob += 1
    return i_glob


lst = []
lst_chat = []


@app.route('/', methods=["POST"])
def process():
    chat_id = request.json["message"]["chat"]["id"]
    try:
        name = request.json["message"]["chat"]["username"]
    except:
        name = "anonimus"
    send_message(chat_id=chat_id, text=request.json["message"]["text"], name=name)
    return {"ok": True}


if __name__ == '__main__':
    serve(app, host='0.0.0.0', port='5000')