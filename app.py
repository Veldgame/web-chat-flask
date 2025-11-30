from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, Message
from config import Config
from sqlalchemy import inspect
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

online_users = set()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def check_tables():
    with db.engine.connect() as conn:  # <-- Получаем Connection
        inspector = inspect(conn)        # <-- Создаём инспектор
        if not inspector.has_table('user'):  # <-- Проверяем таблицу
            with app.app_context():
                db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/api/users')
@login_required
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': user.id,
        'username': user.username
    } for user in users])

@app.route('/api/private-messages/<int:user_id>')
@login_required
def get_private_messages(user_id):
    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == current_user.id) & (PrivateMessage.receiver_id == user_id)) |
        ((PrivateMessage.sender_id == user_id) & (PrivateMessage.receiver_id == current_user.id))
    ).order_by(PrivateMessage.timestamp).all()
    
    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'content': m.content,
        'timestamp': m.timestamp.isoformat(),
        'is_read': m.is_read
    } for m in messages])

@socketio.on('send_private_message')
def handle_private_message(data):
    if not current_user.is_authenticated:
        return

    receiver_id = data['receiver_id']
    
    # Запрет отправки самому себе на сервере
    if receiver_id == current_user.id:
        print("Попытка отправить сообщение самому себе заблокирована")
        return  # Просто игнорируем запрос

    receiver = User.query.get(receiver_id)
    if not receiver:
        return

    message = PrivateMessage(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        content=data['content']
    )
    db.session.add(message)
    db.session.commit()

    emit('private_message', {
        'id': message.id,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'content': message.content,
        'timestamp': message.timestamp.isoformat(),
        'is_read': False,
        'sender_username': current_user.username
    }, room=f'user_{receiver.id}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('chat'))
        else:
            flash('Неверное имя пользователя или пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь уже существует')
            return redirect(url_for('register'))
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Теперь войдите в систему.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/chat')
@login_required
def chat():
    # Получаем последних сообщений для общего чата
    messages = Message.query.filter(Message.receiver_id.is_(None)).order_by(Message.timestamp).all()
    users = User.query.all()
    return render_template('chat.html', messages=messages, users=users)

# Socket.IO события
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        online_users.add(current_user.username)
        join_room('global')
        emit('user_joined', {'username': current_user.username}, broadcast=True)
        emit('online_users', list(online_users), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated and current_user.username in online_users:
        online_users.remove(current_user.username)
        leave_room('global')
        emit('user_left', {'username': current_user.username}, broadcast=True)
        emit('online_users', list(online_users), broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    if not current_user.is_authenticated:
        return
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=data.get('receiver_id'),
        content=data['content']
    )
    db.session.add(message)
    db.session.commit()
    
    emit('new_message', {
        'sender': current_user.username,
        'content': data['content'],
        'timestamp': message.timestamp.isoformat(),
        'receiver_id': data.get('receiver_id')
    }, room='global')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Явное создание таблиц при старте
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)