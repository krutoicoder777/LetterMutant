from flask import Flask, request, jsonify, session, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_session import Session
from config import Config
from database import Database
from ranks_config import RANKS
import logging
import random
import time
import math
import pymorphy3

app = Flask(__name__)
app.config.from_object(Config)

app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600 

Session(app)

socketio = SocketIO(app,
    cors_allowed_origins="*",
    async_mode='threading'
)

db = Database('boggle.db')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rooms = {}
matchmaking_queue = []
disconnected_players = {}

morph = pymorphy3.MorphAnalyzer()

CUBES = [
    ['А', 'А', 'А', 'Е', 'Н', 'Т'],
    ['А', 'Е', 'И', 'И', 'Н', 'С'],
    ['А', 'Е', 'И', 'О', 'Л', 'Р'],
    ['А', 'Е', 'М', 'С', 'Т', 'Т'],
    ['А', 'Е', 'Н', 'Л', 'С', 'Ь'],
    ['А', 'Е', 'Р', 'В', 'К', 'Л'],
    ['А', 'Е', 'Т', 'Н', 'Н', 'И'],
    ['Б', 'О', 'К', 'Л', 'Р', 'Ы'],
    ['В', 'Е', 'Е', 'Е', 'И', 'Й'],
    ['В', 'Л', 'О', 'С', 'И', 'П'],
    ['Д', 'О', 'Л', 'М', 'И', 'Я'],
    ['Е', 'Е', 'Е', 'Н', 'С', 'Т'],
    ['Е', 'И', 'О', 'П', 'Р', 'С'],
    ['Е', 'Р', 'Т', 'Т', 'У', 'О'],
    ['И', 'И', 'Л', 'Н', 'О', 'С'],
    ['И', 'М', 'Т', 'С', 'У', 'А'],
    ['К', 'Н', 'О', 'О', 'Ы', 'Я'],
    ['Л', 'Р', 'Т', 'О', 'А', 'Е'],
    ['М', 'О', 'С', 'В', 'Г', 'А'],
    ['Н', 'Н', 'Р', 'Т', 'И', 'Е'],
    ['О', 'О', 'Л', 'Д', 'Н', 'Е'],
    ['О', 'П', 'Р', 'С', 'С', 'Ы'],
    ['П', 'Е', 'К', 'А', 'Р', 'С'],
    ['Т', 'И', 'А', 'М', 'С', 'О'],
    ['Ь', 'Ы', 'Р', 'М', 'А', 'И']
]

def generate_board():
    board = []
    bonus_positions = random.sample(range(25), random.randint(3, 6))
    for i, cube in enumerate(CUBES):
        letter = random.choice(cube)
        is_bonus = i in bonus_positions
        board.append({'letter': letter, 'is_bonus': is_bonus})
    return board

def calculate_score(word, board_letters):
    if len(word) < 3:
        return 0
    base_score = len(word) - 2
    bonus_count = 0
    for letter in board_letters:
        if letter == word:
            bonus_count += 1
    return base_score + bonus_count

def is_valid_path(word, board):
    if len(word) < 3:
        return False

    word = word.upper()
    letters = [cell['letter'] for cell in board]

    positions = []
    for i, letter in enumerate(letters):
        if letter == word[0]:
            positions.append([i])

    for i in range(1, len(word)):
        new_positions = []
        for path in positions:
            last = path[-1]
            row = last // 5
            col = last % 5

            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr = row + dr
                    nc = col + dc
                    if 0 <= nr < 5 and 0 <= nc < 5:
                        idx = nr * 5 + nc
                        if idx not in path and letters[idx] == word[i]:
                            new_positions.append(path + [idx])
        positions = new_positions
        if not positions:
            return False

    return True

def is_valid_word(word):
    if len(word) < 3:
        logger.info(f"❌ Слово '{word}' отклонено: меньше 3 букв")
        return False
    word = word.lower()
    parsed = morph.parse(word)
    if not parsed:
        logger.info(f"❌ Слово '{word}' отклонено: не найдено в словаре")
        return False
    normal_form = parsed[0].normal_form
    tag = parsed[0].tag
    if not tag or not tag.POS:
        logger.info(f"❌ Слово '{word}' отклонено: не определена часть речи")
        return False
    logger.info(f"✅ Слово '{word}' валидно (нормальная форма: '{normal_form}', часть речи: {tag.POS})")
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or len(username) < 3:
        return jsonify({'error': 'Имя должно быть минимум 3 символа'}), 400

    if not password or len(password) < 4:
        return jsonify({'error': 'Пароль должен быть минимум 4 символа'}), 400

    if db.get_user(username):
        return jsonify({'error': 'Пользователь уже существует'}), 400

    user_id = db.create_user(username, password)

    logger.info(f"Новый пользователь: {username} (id: {user_id})")

    return jsonify({
        'success': True,
        'user_id': user_id,
        'username': username,
        'message': 'Регистрация успешна'
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user_id = db.verify_user(username, password)

    if not user_id:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    session['user_id'] = user_id
    session['username'] = username
    session.modified = True
    session.permanent = True

    stats = db.get_stats(user_id)

    logger.info(f"Вход пользователя: {username} (id: {user_id})")

    return jsonify({
        'success': True,
        'user_id': user_id,
        'username': username,
        'stats': dict(stats) if stats else None
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/leaderboard')
def leaderboard():
    limit = request.args.get('limit', 10, type=int)
    top = db.get_leaderboard(limit)
    return jsonify([dict(row) for row in top])

@app.route('/api/stats/<int:user_id>')
def get_stats(user_id):
    stats = db.get_stats(user_id)
    if not stats:
        return jsonify({'error': 'Игрок не найден'}), 404

    user = db.get_user_by_id(user_id)

    return jsonify({
        'username': user['username'] if user else None,
        'stats': dict(stats)
    })

@app.route('/api/history/<int:user_id>')
def get_history(user_id):
    history = db.get_user_history(user_id)
    return jsonify([dict(row) for row in history])

@app.route('/api/ranks')
def get_ranks():
    return jsonify(RANKS)

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    username = session.get('username')

    if user_id and username:
        logger.info(f"WebSocket подключен: {username} (id: {user_id})")
        emit('connected', {
            'user_id': user_id,
            'username': username,
            'message': f'Добро пожаловать, {username}!'
        })
    else:
        logger.info(f"WebSocket подключен без авторизации: {request.sid}")
        emit('connected', {
            'message': 'Подключено без авторизации'
        })

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    user_id = session.get('user_id')

    for room_id, room in list(rooms.items()):
        if request.sid in room['players']:
            player = room['players'][request.sid]
            if user_id:
                disconnected_players[user_id] = {
                    'room_id': room_id,
                    'name': player['name'],
                    'score': player['score'],
                    'words': player['words']
                }
            del room['players'][request.sid]
            leave_room(room_id)
            if not room['players']:
                del rooms[room_id]
                logger.info(f"Комната {room_id} удалена")
            else:
                socketio.emit('room_update', {
                    'room': room_id,
                    'players': [
                        {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
                        for p in room['players'].values()
                    ],
                    'owner_id': room.get('owner_id'),
                    'game_started': room['game_started']
                }, room=room_id)
            logger.info(f"Игрок {username} отключился из комнаты {room_id}")

    for item in list(matchmaking_queue):
        if item[0] == user_id:
            matchmaking_queue.remove(item)
            socketio.emit('matchmaking_status', {'status': 'cancelled'}, room=request.sid)

@socketio.on('login')
def handle_login(data):
    username = data.get('username', '').strip()
    user_id = session.get('user_id')

    if not user_id:
        emit('login_error', 'Пожалуйста, войдите через HTTP сначала')
        return

    user = db.get_user_by_id(user_id)
    if not user:
        emit('login_error', 'Пользователь не найден')
        return

    if user['username'] != username:
        emit('login_error', 'Имя пользователя не совпадает с сессией')
        return

    stats = db.get_stats(user_id)

    emit('login_success', {
        'user_id': user_id,
        'username': user['username'],
        'rating': stats['rating'] if stats else 0,
        'rank': stats['rank'] if stats else 'Амёба'
    })

    if user_id in disconnected_players:
        data = disconnected_players.pop(user_id)
        room_id = data['room_id']
        if room_id in rooms:
            room = rooms[room_id]
            room['players'][request.sid] = {
                'name': data['name'],
                'user_id': user_id,
                'score': data['score'],
                'words': data['words']
            }
            join_room(room_id)
            socketio.emit('room_update', {
                'room': room_id,
                'players': [
                    {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
                    for p in room['players'].values()
                ],
                'owner_id': room.get('owner_id'),
                'game_started': room['game_started']
            }, room=room_id)
            if room['game_started']:
                emit('game_start', {
                    'board': room['board'],
                    'duration': room['timer'],
                    'scores': {p['name']: p['score'] for p in room['players'].values()}
                }, room=request.sid)
            logger.info(f"Игрок {username} восстановлен в комнате {room_id}")

@socketio.on('get_leaderboard')
def handle_get_leaderboard():
    top = db.get_leaderboard(10)
    emit('leaderboard', [dict(row) for row in top])

@socketio.on('create_room')
def handle_create_room(data):
    user_id = session.get('user_id')
    username = session.get('username')

    if not user_id:
        emit('error', 'Необходимо войти в систему')
        return

    room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

    rooms[room_id] = {
        'type': 'custom',
        'players': {},
        'board': None,
        'game_started': False,
        'timer': 60,
        'used_words': set(),
        'owner_id': user_id,
        'max_players': 10,
        'countdown': 0
    }

    rooms[room_id]['players'][request.sid] = {
        'name': username,
        'user_id': user_id,
        'score': 0,
        'words': []
    }

    join_room(room_id)

    emit('room_created', {
        'room': room_id
    }, room=request.sid)

    socketio.emit('room_update', {
        'room': room_id,
        'players': [
            {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
            for p in rooms[room_id]['players'].values()
        ],
        'owner_id': user_id,
        'game_started': False
    }, room=room_id)

    logger.info(f"Создана комната {room_id} создателем {username}")

@socketio.on('join_room')
def handle_join_room(data):
    user_id = session.get('user_id')
    username = session.get('username')
    room_id = data.get('room', '').upper().strip()

    if not user_id:
        emit('error', 'Необходимо войти в систему')
        return

    if room_id not in rooms:
        emit('error', 'Комната не найдена')
        return

    room = rooms[room_id]

    if room['game_started']:
        emit('error', 'Игра уже началась')
        return

    if len(room['players']) >= room['max_players']:
        emit('error', 'Комната заполнена')
        return

    room['players'][request.sid] = {
        'name': username,
        'user_id': user_id,
        'score': 0,
        'words': []
    }

    join_room(room_id)

    emit('room_joined', {
        'room': room_id
    }, room=request.sid)

    socketio.emit('room_update', {
        'room': room_id,
        'players': [
            {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
            for p in room['players'].values()
        ],
        'owner_id': room['owner_id'],
        'game_started': False
    }, room=room_id)

    logger.info(f"Игрок {username} присоединился к комнате {room_id}")

@socketio.on('quick_play')
def handle_quick_play(data):
    user_id = session.get('user_id')
    username = session.get('username')

    if not user_id:
        emit('error', 'Необходимо войти в систему')
        return

    for item in matchmaking_queue:
        if item[0] == user_id:
            emit('matchmaking_status', {'status': 'already_in_queue'}, room=request.sid)
            return

    matchmaking_queue.append((user_id, request.sid))
    queue_position = len(matchmaking_queue)
    emit('matchmaking_status', {'status': 'waiting', 'position': queue_position}, room=request.sid)
    logger.info(f"Игрок {username} добавлен в очередь поиска (позиция {queue_position})")

    if len(matchmaking_queue) >= 2:
        logger.info(f"Найдено {len(matchmaking_queue)} игроков, запускаем игру")
        start_ranked_game()

@socketio.on('leave_matchmaking')
def handle_leave_matchmaking(data):
    user_id = session.get('user_id')
    username = session.get('username')

    for item in list(matchmaking_queue):
        if item[0] == user_id:
            matchmaking_queue.remove(item)
            emit('matchmaking_status', {'status': 'cancelled'}, room=request.sid)
            logger.info(f"Игрок {username} покинул очередь поиска")
            return

def start_ranked_game():
    global matchmaking_queue

    if len(matchmaking_queue) < 2:
        return

    players = matchmaking_queue[:4]
    matchmaking_queue = matchmaking_queue[4:]

    room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

    rooms[room_id] = {
        'type': 'ranked',
        'players': {},
        'board': None,
        'game_started': False,
        'timer': 60,
        'used_words': set(),
        'owner_id': None,
        'max_players': 4,
        'countdown': 10
    }

    player_sids = []
    for user_id, sid in players:
        user = db.get_user_by_id(user_id)
        if user:
            username = user['username']
            rooms[room_id]['players'][sid] = {
                'name': username,
                'user_id': user_id,
                'score': 0,
                'words': []
            }
            join_room(room_id, sid=sid)
            player_sids.append(sid)
            logger.info(f"Игрок {username} добавлен в комнату {room_id}")

    for sid in player_sids:
        socketio.emit('room_joined', {'room': room_id}, room=sid)
        socketio.emit('matchmaking_status', {'status': 'found'}, room=sid)

    socketio.emit('room_update', {
        'room': room_id,
        'players': [
            {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
            for p in rooms[room_id]['players'].values()
        ],
        'owner_id': None,
        'game_started': False,
        'countdown': 10
    }, room=room_id)

    socketio.start_background_task(ranked_countdown, room_id)

def ranked_countdown(room_id):
    if room_id not in rooms:
        return

    room = rooms[room_id]

    for i in range(10, 0, -1):
        if room_id not in rooms or room['game_started']:
            break
        room['countdown'] = i
        socketio.emit('room_update', {
            'room': room_id,
            'players': [
                {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
                for p in room['players'].values()
            ],
            'owner_id': room.get('owner_id'),
            'game_started': False,
            'countdown': i
        }, room=room_id)
        time.sleep(1)

    if room_id in rooms and not rooms[room_id]['game_started']:
        start_game(room_id)

@socketio.on('start_game')
def handle_start_game(data):
    room_id = data.get('room')
    user_id = session.get('user_id')

    if room_id not in rooms:
        emit('error', 'Комната не найдена')
        return

    room = rooms[room_id]

    if room['type'] == 'custom' and room['owner_id'] != user_id:
        emit('error', 'Только создатель может начать игру')
        return

    if room['game_started']:
        emit('error', 'Игра уже началась')
        return

    if len(room['players']) < 1:
        emit('error', 'Нет игроков для начала игры')
        return

    start_game(room_id)

def start_game(room_id):
    if room_id not in rooms:
        return

    room = rooms[room_id]

    board_data = generate_board()
    room['board'] = board_data
    room['game_started'] = True
    room['timer'] = 60
    room['used_words'] = set()

    for player in room['players'].values():
        player['score'] = 0
        player['words'] = []

    socketio.emit('game_start', {
        'board': board_data,
        'duration': room['timer'],
        'scores': {p['name']: p['score'] for p in room['players'].values()}
    }, room=room_id)

    socketio.start_background_task(game_timer, room_id)

    logger.info(f"Игра началась в комнате {room_id}")

def game_timer(room_id):
    while True:
        if room_id not in rooms:
            break

        room = rooms[room_id]

        if not room['game_started']:
            break

        time.sleep(1)
        room['timer'] -= 1

        socketio.emit('timer_update', {'timer': room['timer']}, room=room_id)

        if room['timer'] <= 0:
            break

    if room_id in rooms and rooms[room_id]['game_started']:
        end_game(room_id)

@socketio.on('time_up')
def handle_time_up(data):
    room_id = data.get('room')
    if room_id in rooms and rooms[room_id]['game_started']:
        end_game(room_id)

def end_game(room_id):
    if room_id not in rooms:
        return

    room = rooms[room_id]
    room['game_started'] = False

    players_data = []
    for sid, player in room['players'].items():
        players_data.append({
            'name': player['name'],
            'user_id': player['user_id'],
            'score': player['score'],
            'words': player['words']
        })

    winner = max(players_data, key=lambda p: p['score']) if players_data else None

    socketio.emit('game_end', {
        'winner': winner['name'] if winner else 'Никто',
        'results': players_data
    }, room=room_id)

    if room['type'] == 'ranked' and winner:
        save_ranked_results(room_id, players_data, winner)

    logger.info(f"Игра в комнате {room_id} завершена. Победитель: {winner['name'] if winner else 'Никто'}")

def save_ranked_results(room_id, players_data, winner):
    room = rooms.get(room_id)
    if not room:
        return

    board_letters = [cell['letter'] for cell in room['board']]

    words_data = []
    for player in players_data:
        for word in player['words']:
            points = calculate_score(word, board_letters)
            words_data.append({
                'user_id': player['user_id'],
                'word': word,
                'points': points
            })

    db.save_game_with_rating(
        room_id,
        players_data,
        words_data,
        winner['user_id'],
        duration=60
    )

@socketio.on('submit_word')
def handle_submit_word(data):
    room_id = data.get('room')
    word = data.get('word', '').upper().strip()
    user_id = session.get('user_id')

    logger.info(f"📝 Получено слово: '{word}' от пользователя {user_id} в комнате {room_id}")

    if not user_id:
        emit('error', 'Необходимо войти в систему')
        return

    if room_id not in rooms:
        emit('error', 'Комната не найдена')
        return

    room = rooms[room_id]

    if not room['game_started']:
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Игра не активна'
        })
        return

    if request.sid not in room['players']:
        emit('error', 'Вы не в этой комнате')
        return

    player = room['players'][request.sid]

    if len(word) < 3:
        logger.info(f"❌ Слово '{word}' отклонено: меньше 3 букв")
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Слово должно быть минимум 3 буквы'
        })
        return

    if word in room['used_words']:
        logger.info(f"❌ Слово '{word}' отклонено: уже использовано в этой игре")
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Это слово уже использовано'
        })
        return

    if word in player['words']:
        logger.info(f"❌ Слово '{word}' отклонено: игрок уже вводил это слово")
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Вы уже вводили это слово'
        })
        return

    if not is_valid_word(word):
        logger.info(f"❌ Слово '{word}' отклонено: не найдено в словаре")
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Слово не найдено в словаре'
        })
        return

    board_letters = [cell['letter'] for cell in room['board']]

    if not is_valid_path(word, room['board']):
        logger.info(f"❌ Слово '{word}' отклонено: нельзя собрать на доске")
        emit('word_result', {
            'valid': False,
            'word': word,
            'message': 'Нельзя собрать на доске'
        })
        return

    points = calculate_score(word, board_letters)
    player['score'] += points
    player['words'].append(word)
    room['used_words'].add(word)

    logger.info(f"✅ Слово '{word}' принято! +{points} очков (всего: {player['score']})")

    emit('word_result', {
        'valid': True,
        'word': word,
        'score': player['score'],
        'message': ''
    }, room=request.sid)

    socketio.emit('room_update', {
        'room': room_id,
        'players': [
            {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
            for p in room['players'].values()
        ],
        'owner_id': room.get('owner_id'),
        'game_started': True
    }, room=room_id)

@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data.get('room')

    if room_id in rooms:
        if request.sid in rooms[room_id]['players']:
            username = rooms[room_id]['players'][request.sid]['name']
            del rooms[room_id]['players'][request.sid]
            leave_room(room_id)

            if not rooms[room_id]['players']:
                del rooms[room_id]
                logger.info(f"Комната {room_id} удалена")
            else:
                socketio.emit('room_update', {
                    'room': room_id,
                    'players': [
                        {'name': p['name'], 'score': p['score'], 'user_id': p['user_id']}
                        for p in rooms[room_id]['players'].values()
                    ],
                    'owner_id': rooms[room_id].get('owner_id'),
                    'game_started': rooms[room_id]['game_started']
                }, room=room_id)
            emit('room_left', {'room': room_id}, room=request.sid)
            logger.info(f"Игрок {username} покинул комнату {room_id}")

@socketio.on('get_state')
def handle_get_state(data):
    room_id = data.get('room')

    if not room_id or room_id not in rooms:
        emit('game_state', {'state': 'lobby'})
        return

    room = rooms[room_id]

    if room['game_started']:
        emit('game_state', {
            'state': 'playing',
            'board': room['board'],
            'timer': room['timer'],
            'scores': {p['name']: p['score'] for p in room['players'].values()}
        }, room=request.sid)
    else:
        emit('game_state', {
            'state': 'lobby',
            'room': room_id
        }, room=request.sid)

@socketio.on('ping')
def handle_ping():
    emit('pong', {'message': 'Pong!'})

if __name__ == '__main__':
    print("=" * 50)
    print("🧬 LetterMutant Game Server")
    print("=" * 50)
    print(f"📁 База данных: boggle.db")
    print(f"🌐 Сервер запущен на http://localhost:5000")
    print("=" * 50)

    socketio.run(app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )
