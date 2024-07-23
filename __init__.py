import flask as fl
from flask import Flask, render_template, request, redirect, url_for, jsonify
import flask_sqlalchemy as fsql
from flask_sqlalchemy import SQLAlchemy
import time
import json
from uuid import uuid1

SESSION_TIME = 1800
data = {"session_id": -1, "data": []}
n = 1

db = SQLAlchemy()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///to_do_list.db'
db.init_app(app)


class ToDoList(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_email = db.Column(db.String(250), nullable=False)
    list_input = db.Column(db.String(500), nullable=False)
    list_name = db.Column(db.String(250), nullable=False)
    # todo_json = db.Column(db.String(500), nullable=False)  # ??? what was this--the whole 'data' json?
    date_due = db.Column(db.String(250), nullable=False) # synthesized via datetime or whatever from month day year fields
    # date_created = db.Column(db.String(250), nullable=False)  /// don't think i have to know this per se
    hours_left = db.Column(db.Integer, nullable=False)
    item_category = db.Column(db.String(250), nullable=False)
    item_done = db.Column(db.String(250), default='False', nullable=False)
    # priority = db.Column(db.Float, nullable=False)


class Users(db.Model):
    user_email = db.Column(db.String(250), primary_key=True, nullable=False)
    session_id = db.Column(db.Integer, unique=True)
    last_transaction = db.Column(db.String(250))
    user_password = db.Column(db.String(250), nullable=False)


with app.app_context():
    print("creating database")
    db.create_all()


def jsonise(this_data):
    my_data = {'session_id': data['session_id'], 'data': []}
    Columns = [column.key for column in ToDoList.__table__.columns]
    for record in this_data:
        a_record = {}
        for column in Columns:
            a_record[column] = eval('record.' + column)
        my_data["data"].append(a_record)
    return my_data


def process_list_items(user_email):
    global data, n
    with app.app_context():
        for item in data['data']:
            if item['action'] == 'insert':
                db.session.execute(db.insert(ToDoList).values(user_email=user_email, list_name=item['list_name'],
                        list_input=item['list_input'], item_category=item['item_category'], date_due=item['date_due'],
                        hours_left=item['hours_left']))
            elif item['action'] == 'delete':
                db.session.execute(db.delete(ToDoList).where(ToDoList.user_email == user_email, ToDoList.list_name == item['list_name'],
                                                             ToDoList.list_input == item['list_input']))
            elif item['action'] == 'update':
                record = db.session.execute(db.select(ToDoList).where(ToDoList.user_email == user_email, ToDoList.list_name == item['list_name'])).scalar()
                record.item_done = item['item_done']
            db.session.commit()

### print out versions of dependencies


@app.route('/', methods=['GET', 'POST'])
def home():
    global data
    # print("fl.__version__ is " + fl.__version__)
    # print("fsql.__version__ is " + fsql.__version__)
    if data['session_id'] != -1:
        session_id = data['session_id']
        with app.app_context():
            user_email = db.session.execute(db.select(Users.user_email).where(Users.session_id == session_id)).scalar()
            print(f"user_email is {user_email}")
            # last_record = db.session.execute(db.select(ToDoList).order_by(ToDoList.id.desc())).limit(1).scalar()
            if len(user_email) > 0:
                result = db.session.execute(db.select(ToDoList).where(ToDoList.user_email == user_email)).scalars()
                if result != None:
                    my_data = jsonise(result)
                    json_data = json.dumps(my_data)
                    data = json.loads(json_data)
                    data['session_id'] = session_id
                return render_template('index.html', data=data)

    else:
        data['data'] = []
        data['session_id'] = -1
        return render_template('index.html', data=data)


@app.route('/save_items', methods=['POST'])
def save_list_items():
    global data
    json_data = request.form.get('json_data')
    print(f"incoming json (/save_items) is {json_data}")
    data = json.loads(json_data)
    with app.app_context():
        authenticate_result = db.session.execute(db.select(Users).where(Users.session_id == data['session_id'])).scalar()
        if authenticate_result is not None:
            time_now = int(time.time())
            if time_now - int(authenticate_result.last_transaction) > SESSION_TIME:
                data['session_id'] = -1
                return redirect('/flask_app_2/')
            else:
                authenticate_result.last_transaction = time_now
                db.session.commit()
                process_list_items(authenticate_result.user_email)
                return redirect('/flask_app_2')
        else:
            data['session_id'] = -1
            data['data'] = []
            return redirect('/flask_app_2')


@app.route('/login', methods=['POST'])
def do_login():
    global data
    user_email = request.form.get("user_email")
    user_password = request.form.get("user_password")
    json_data = request.form.get('json_field')
    print(f"raw json data is {json_data}")
    data = json.loads(json_data)
    session_id = uuid1().hex
    # print(f"session_id is {session_id}, user_email is {user_email} and user_password is {user_password}")

    with app.app_context():
        email_result = db.session.execute(db.select(Users).where(Users.user_email == user_email, Users.user_password == user_password)).scalar()
        # password_result = db.session.execute(db.select(Users).where(Users.user_password == user_password)).scalar()
        if email_result is not None:
            result = email_result
            result.session_id = session_id
            result.last_transaction = int(time.time())
            print(f"result.session_id is {result.session_id}, result.last_transaction is {result.last_transaction}")
            db.session.add(result)
            db.session.commit()
            data['session_id'] = session_id
            if len(data['data']) > 0:
                process_list_items(user_email)
                #all_data = db.session.execute(db.select(ToDoList).where(ToDoList.user_email == users.user_email)).scalars()
                # json_data = jsonise(all_data)
                # print(f"retval from jsonise is {json_data}")
                # session_json = json.loads(json_data)
            return redirect("/flask_app_2")
        else:
            data['session_id'] = -1
            print("email_result must have been none.")
            print(f"data before render is: \n{data}")
            return render_template('index.html', data=data)


@app.route('/test', methods=['GET'])
def test():
    return "<h1>It worked!</h1>\n"


@app.route('/logout', methods=['POST'])
def logout():
    data['data'] = []
    data['session_id'] = -1
    return render_template('index.html', data=data)


@app.route('/register', methods=['POST'])
def do_register():
    global data
    print("do_register() has been reached")
    users = Users()
    users.user_email = request.form.get("user_email")
    users.user_password = request.form.get("user_password")
    json_data = request.form.get("json_field")
    print(f"submitted email is {users.user_email} and submitted password is {users.user_password}") 
    print(json_data)
    users.session_id = uuid1().hex
    users.last_transaction = int(time.time())
    

    if json_data is not None:
        data = json.loads(json_data)
        if len(data['data']) > 0:
            process_list_items(users.user_email)

    data["session_id"] = users.session_id
    with app.app_context():
        # db.session.execute(db.insert(Users).values(user_email=users.user_email, user_password=users.user_password,
                                                   # session_id=users.session_id, last_transaction=users.last_transaction))
        db.session.add(users)
        db.session.commit()

    session_id = json.dumps(data)
    session_json = json.loads(session_id)
    print(session_json)
    return render_template('index.html', data=session_json)


if __name__ == '__main__':
    app.run()

