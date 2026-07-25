const socket = io();

let currentUser = null;
let currentRoom = null;
let isOwner = false;
let gameState = 'lobby';
let selectedCells = [];
let boardData = [];
let myWords = [];
let timerInterval = null;
let gameTimer = 60;
let inMatchmaking = false;

const elements = {
    auth: document.getElementById('auth'),
    app: document.getElementById('app'),
    username: document.getElementById('username'),
    password: document.getElementById('password'),
    loginBtn: document.getElementById('login-btn'),
    registerBtn: document.getElementById('register-btn'),
    logoutBtn: document.getElementById('logout-btn'),
    userDisplay: document.getElementById('user-display'),
    ratingDisplay: document.getElementById('rating-display'),
    rankDisplay: document.getElementById('rank-display'),
    lobby: document.getElementById('lobby'),
    room: document.getElementById('room'),
    game: document.getElementById('game'),
    roomCodeDisplay: document.getElementById('room-code-display'),
    roomPlayers: document.getElementById('room-players'),
    roomStatus: document.getElementById('room-status'),
    startBtn: document.getElementById('start-btn'),
    leaveRoomBtn: document.getElementById('leave-room-btn'),
    createRoomBtn: document.getElementById('create-room-btn'),
    joinRoomBtn: document.getElementById('join-room-btn'),
    joinInput: document.getElementById('join-input'),
    joinConfirmBtn: document.getElementById('join-confirm-btn'),
    joinCancelBtn: document.getElementById('join-cancel-btn'),
    quickPlayBtn: document.getElementById('quick-play-btn'),
    matchmakingStatus: document.getElementById('matchmaking-status'),
    matchmakingText: document.getElementById('matchmaking-text'),
    queuePosition: document.getElementById('queue-position'),
    cancelMatchmakingBtn: document.getElementById('cancel-matchmaking-btn'),
    board: document.getElementById('board'),
    currentWord: document.getElementById('current-word'),
    submitBtn: document.getElementById('submit-btn'),
    clearBtn: document.getElementById('clear-btn'),
    myWordsList: document.getElementById('my-words-list'),
    scoresList: document.getElementById('scores-list'),
    myScore: document.getElementById('my-score'),
    timerText: document.getElementById('timer-text'),
    timerProgress: document.getElementById('timer-progress'),
    leaderboardList: document.getElementById('leaderboard-list'),
    modal: document.getElementById('modal'),
    modalTitle: document.getElementById('modal-title'),
    modalBody: document.getElementById('modal-body'),
    modalClose: document.getElementById('modal-close'),
    modalActionBtn: document.getElementById('modal-action-btn'),
    statusMessage: document.getElementById('status-message'),
    welcomeName: document.getElementById('welcome-name'),
    roomBadge: document.getElementById('room-badge'),
    roomCode: document.getElementById('room-code'),
    scoresDisplay: document.getElementById('scores-display')
};

socket.on('connect', () => {
    console.log('Подключено к серверу');
    if (currentUser && currentUser.username) {
        socket.emit('login', { username: currentUser.username });
    } else {
        const savedUsername = localStorage.getItem('username');
        if (savedUsername) {
            socket.emit('login', { username: savedUsername });
        }
    }
});

socket.on('disconnect', () => {
    console.log('Отключено от сервера');
    stopTimer();
});

socket.on('connect_error', (err) => {
    console.error('Ошибка подключения:', err);
    showStatus('Ошибка подключения к серверу', 'danger');
});

socket.on('login_success', (data) => {
    console.log('Вход выполнен:', data.username);
    currentUser = data;
    updateProfile(data);
    showApp(true);
    setState('lobby');
    fetchLeaderboard();
    showStatus('Добро пожаловать, ' + data.username + '!', 'success');
    localStorage.setItem('username', data.username);
});

socket.on('login_error', (msg) => {
    console.error('Ошибка входа:', msg);
    showStatus('Ошибка: ' + msg, 'danger');
});

socket.on('leaderboard', (data) => {
    renderLeaderboard(data);
});

socket.on('room_created', (data) => {
    console.log('Комната создана:', data.room);
    currentRoom = data.room;
    isOwner = true;
    showRoomCode(data.room);
    enterRoom({ room: data.room, players: [], owner_id: currentUser ? currentUser.user_id : null });
});

socket.on('room_joined', (data) => {
    console.log('Присоединились к комнате:', data.room);
    currentRoom = data.room;
    isOwner = false;
    showRoomCode(data.room);
    enterRoom({ room: data.room, players: [], owner_id: null });
});

socket.on('room_update', (data) => {
    console.log('Обновление комнаты:', data);
    if (data.room) {
        currentRoom = data.room;
        showRoomCode(data.room);
    }
    if ((data.room || data.countdown !== undefined) && gameState !== 'room' && gameState !== 'playing') {
        setState('room');
        if (data.room) showRoomCode(data.room);
    }
    updateRoom(data);
});

socket.on('room_left', () => {
    console.log('Покинули комнату');
    leaveRoomCleanup();
});

socket.on('matchmaking_status', (data) => {
    console.log('Статус поиска:', data);
    if (data.status === 'waiting') {
        inMatchmaking = true;
        if (elements.matchmakingStatus) {
            elements.matchmakingStatus.style.display = 'block';
        }
        if (elements.queuePosition) {
            elements.queuePosition.textContent = data.position || 0;
        }
        if (elements.matchmakingText) {
            elements.matchmakingText.innerHTML = 'Поиск соперника... Позиция в очереди: <span id="queue-position">' + (data.position || 0) + '</span>';
        }
    } else if (data.status === 'found') {
        inMatchmaking = false;
        if (elements.matchmakingStatus) {
            elements.matchmakingStatus.style.display = 'none';
        }
        showStatus('Соперник найден! Игра начинается...', 'success');
    } else if (data.status === 'cancelled') {
        inMatchmaking = false;
        if (elements.matchmakingStatus) {
            elements.matchmakingStatus.style.display = 'none';
        }
        showStatus('Поиск отменён', 'info');
    } else if (data.status === 'already_in_queue') {
        showStatus('Вы уже в очереди', 'warning');
    }
});

socket.on('game_start', (data) => {
    console.log('Игра началась');
    inMatchmaking = false;
    if (elements.matchmakingStatus) {
        elements.matchmakingStatus.style.display = 'none';
    }
    startGame(data);
});

socket.on('timer_update', (data) => {
    updateTimer(data.timer);
});

socket.on('game_end', (data) => {
    console.log('Игра завершена');
    endGame(data);
});

socket.on('word_result', (data) => {
    console.log('Результат слова:', data.word, data.valid ? '✅' : '❌');
    if (data.valid) {
        myWords.push(data.word);
        renderMyWords();
        if (elements.myScore) {
            elements.myScore.textContent = data.score || 0;
        }
        showStatus('Слово "' + data.word + '" принято! +' + (data.score || 0), 'success');
    } else {
        showStatus(data.message || 'Слово не подходит', 'danger');
    }
    clearSelection();
});

socket.on('game_state', (data) => {
    console.log('Восстановление состояния игры');
    if (data.state === 'playing') {
        restoreGame(data);
    } else if (data.state === 'ended') {
        endGame(data);
    } else {
        setState('room');
        if (data.room) {
            currentRoom = data.room;
            showRoomCode(data.room);
            if (elements.room) {
                elements.room.style.display = 'block';
            }
        }
    }
});

socket.on('error', (msg) => {
    console.error('Ошибка:', msg);
    showStatus('Ошибка: ' + msg, 'danger');
});

function showApp(show) {
    if (elements.auth) {
        elements.auth.style.display = show ? 'none' : 'block';
    }
    if (elements.app) {
        elements.app.style.display = show ? 'block' : 'none';
    }
}

function updateProfile(data) {
    if (elements.userDisplay) {
        elements.userDisplay.textContent = data.username;
    }
    if (elements.welcomeName) {
        elements.welcomeName.textContent = data.username;
    }
    if (elements.ratingDisplay) {
        elements.ratingDisplay.textContent = '⭐ ' + (data.rating || 0);
    }
    if (elements.rankDisplay) {
        elements.rankDisplay.textContent = data.rank || 'Новичок';
    }

    if (elements.ratingDisplay) {
        elements.ratingDisplay.style.cursor = 'pointer';
        elements.ratingDisplay.title = 'Кликните для просмотра истории игр';
        elements.ratingDisplay.addEventListener('click', () => fetchHistory());
    }

    if (elements.rankDisplay) {
        elements.rankDisplay.style.cursor = 'pointer';
        elements.rankDisplay.title = 'Кликните для просмотра таблицы рангов';
        elements.rankDisplay.addEventListener('click', () => fetchRanks());
    }
}

function setState(state) {
    gameState = state;
    if (elements.lobby) {
        elements.lobby.style.display = (state === 'lobby') ? 'block' : 'none';
    }
    if (elements.room) {
        elements.room.style.display = (state === 'room') ? 'block' : 'none';
    }
    if (elements.game) {
        elements.game.style.display = (state === 'playing') ? 'block' : 'none';
    }
}

function showStatus(msg, type) {
    const el = elements.statusMessage;
    if (!el) return;
    el.textContent = msg;
    el.className = 'alert mt-3';
    if (type === 'danger') el.classList.add('alert-danger');
    else if (type === 'success') el.classList.add('alert-success');
    else if (type === 'info') el.classList.add('alert-info');
    else if (type === 'warning') el.classList.add('alert-warning');
    else el.classList.add('alert-secondary');
    el.style.display = 'block';
    setTimeout(() => {
        el.style.display = 'none';
    }, 3000);
}

function showRoomCode(code) {
    if (elements.roomCode) {
        elements.roomCode.textContent = code;
    }
    if (elements.roomCodeDisplay) {
        elements.roomCodeDisplay.textContent = code;
    }
    if (elements.roomBadge) {
        elements.roomBadge.style.display = 'inline';
    }
}

function fetchLeaderboard() {
    socket.emit('get_leaderboard');
}

function renderLeaderboard(data) {
    const list = elements.leaderboardList;
    if (!list) return;
    list.innerHTML = '';
    if (!data || data.length === 0) {
        list.innerHTML = '<li class="list-group-item text-muted text-center">Нет игроков</li>';
        return;
    }
    data.forEach((item, index) => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '#' + (index + 1);
        li.innerHTML = `
            <span><strong>${medal}</strong> ${item.username}</span>
            <span class="badge bg-warning rounded-pill">${item.rating || 0}</span>
        `;
        list.appendChild(li);
    });
}

function enterRoom(data) {
    setState('room');
    updateRoom(data);
}

function updateRoom(data) {
    const list = elements.roomPlayers;
    if (!list) return;
    list.innerHTML = '';
    
    if (data.players && data.players.length > 0) {
        data.players.forEach(p => {
            const li = document.createElement('li');
            li.className = 'list-group-item d-flex justify-content-between align-items-center';
            const isOwnerFlag = (p.user_id === data.owner_id);
            li.innerHTML = `
                ${p.name}
                ${isOwnerFlag ? '<span class="badge bg-warning">👑</span>' : ''}
                <span class="badge bg-secondary">${p.score || 0}</span>
            `;
            list.appendChild(li);
        });
    } else {
        list.innerHTML = '<li class="list-group-item text-muted">Ожидание игроков...</li>';
    }
    
    if (data.owner_id && currentUser) {
        isOwner = (data.owner_id === currentUser.user_id);
        if (elements.startBtn) {
            elements.startBtn.style.display = isOwner ? 'inline-block' : 'none';
        }
    }
    
    if (data.status && elements.roomStatus) {
        elements.roomStatus.textContent = data.status;
    }
    
    if (data.countdown !== undefined && data.countdown > 0 && elements.roomStatus) {
        elements.roomStatus.textContent = 'Игра начнётся через ' + data.countdown + 'с';
        elements.roomStatus.className = 'alert alert-warning text-center';
    } else if (elements.roomStatus) {
        elements.roomStatus.className = 'alert alert-secondary text-center';
    }
    
    if (data.game_started) {
        setState('playing');
    }
    
    if (data.players && data.players.length > 0) {
        const scores = {};
        data.players.forEach(p => {
            scores[p.name] = p.score || 0;
        });
        updateScores(scores);
    }
}

function leaveRoomCleanup() {
    currentRoom = null;
    isOwner = false;
    inMatchmaking = false;
    if (elements.matchmakingStatus) {
        elements.matchmakingStatus.style.display = 'none';
    }
    setState('lobby');
    stopTimer();
    selectedCells = [];
    myWords = [];
    boardData = [];
    if (elements.board) {
        elements.board.innerHTML = '';
    }
    if (elements.currentWord) {
        elements.currentWord.textContent = '—';
    }
    if (elements.myWordsList) {
        elements.myWordsList.innerHTML = '<li class="list-group-item text-muted">Пока ничего</li>';
    }
    if (elements.scoresList) {
        elements.scoresList.innerHTML = '<li class="list-group-item text-muted">Ожидаем...</li>';
    }
    if (elements.myScore) {
        elements.myScore.textContent = '0';
    }
    if (elements.timerText) {
        elements.timerText.textContent = '60';
    }
    updateTimerProgress(60);
    if (elements.roomBadge) {
        elements.roomBadge.style.display = 'none';
    }
    if (elements.startBtn) {
        elements.startBtn.style.display = 'none';
    }
}

function startGame(data) {
    setState('playing');
    myWords = [];
    selectedCells = [];
    gameTimer = data.duration || 60;
    boardData = data.board || [];
    renderBoard(boardData);
    if (elements.currentWord) {
        elements.currentWord.textContent = '—';
    }
    if (elements.myWordsList) {
        elements.myWordsList.innerHTML = '<li class="list-group-item text-muted">Пока ничего</li>';
    }
    if (elements.myScore) {
        elements.myScore.textContent = '0';
    }
    if (data.scores) {
        updateScores(data.scores);
    }
    startTimer(gameTimer);
}

function restoreGame(data) {
    setState('playing');
    boardData = data.board || [];
    renderBoard(boardData);
    if (data.words && data.words.length > 0) {
        myWords = data.words;
        renderMyWords();
    }
    if (data.scores) {
        updateScores(data.scores);
        if (currentUser && data.scores[currentUser.username] !== undefined && elements.myScore) {
            elements.myScore.textContent = data.scores[currentUser.username];
        }
    }
    if (data.timer !== undefined) {
        gameTimer = data.timer;
        startTimer(gameTimer);
    }
    if (elements.currentWord) {
        elements.currentWord.textContent = '—';
    }
    selectedCells = [];
}

function renderBoard(board) {
    const boardEl = elements.board;
    if (!boardEl) return;
    boardEl.innerHTML = '';
    
    if (!board || !Array.isArray(board)) {
        console.error('Ошибка: доска не является массивом', board);
        return;
    }
    
    board.forEach((cell, index) => {
        const div = document.createElement('div');
        div.className = 'col p-1';
        const inner = document.createElement('div');
        inner.className = 'cube';
        if (cell && cell.is_bonus) {
            inner.classList.add('bonus');
        }
        inner.textContent = cell ? cell.letter || '?' : '?';
        inner.dataset.index = index;
        inner.addEventListener('click', () => handleCellClick(index));
        div.appendChild(inner);
        boardEl.appendChild(div);
    });
}

function handleCellClick(index) {
    if (gameState !== 'playing' || !timerInterval) {
        return;
    }
    const pos = selectedCells.indexOf(index);
    if (pos !== -1) {
        selectedCells = selectedCells.slice(0, pos);
        updateWordDisplay();
        highlightCells();
        return;
    }
    if (selectedCells.length > 0) {
        const last = selectedCells[selectedCells.length - 1];
        const lastRow = Math.floor(last / 5);
        const lastCol = last % 5;
        const currentRow = Math.floor(index / 5);
        const currentCol = index % 5;
        if (Math.abs(lastRow - currentRow) > 1 || Math.abs(lastCol - currentCol) > 1) {
            return;
        }
    }
    selectedCells.push(index);
    updateWordDisplay();
    highlightCells();
}

function updateWordDisplay() {
    let word = '';
    selectedCells.forEach(idx => {
        if (boardData[idx]) {
            word += boardData[idx].letter;
        }
    });
    if (elements.currentWord) {
        elements.currentWord.textContent = word || '—';
    }
}

function highlightCells() {
    document.querySelectorAll('.cube').forEach((cube) => {
        cube.classList.remove('selected');
        const idx = parseInt(cube.dataset.index);
        if (selectedCells.includes(idx)) {
            cube.classList.add('selected');
        }
    });
}

function clearSelection() {
    selectedCells = [];
    updateWordDisplay();
    highlightCells();
}

function startTimer(seconds) {
    stopTimer();
    gameTimer = seconds;
    updateTimerUI(seconds);
    timerInterval = setInterval(() => {
        gameTimer -= 1;
        if (gameTimer <= 0) {
            gameTimer = 0;
            updateTimerUI(0);
            stopTimer();
            socket.emit('time_up', { room: currentRoom });
        } else {
            updateTimerUI(gameTimer);
        }
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function updateTimer(seconds) {
    gameTimer = seconds;
    updateTimerUI(seconds);
}

function updateTimerUI(seconds) {
    if (elements.timerText) {
        elements.timerText.textContent = seconds;
    }
    updateTimerProgress(seconds);
    if (seconds <= 5) {
        if (elements.timerText) {
            elements.timerText.style.color = '#dc3545';
        }
    } else if (seconds <= 10) {
        if (elements.timerText) {
            elements.timerText.style.color = '#ffc107';
        }
    } else {
        if (elements.timerText) {
            elements.timerText.style.color = '#fff';
        }
    }
}

function updateTimerProgress(seconds) {
    const progressEl = elements.timerProgress;
    if (!progressEl) return;
    const circumference = 2 * Math.PI * 45;
    const progress = (seconds / 60) * circumference;
    progressEl.style.strokeDasharray = circumference;
    progressEl.style.strokeDashoffset = circumference - progress;
    if (seconds <= 5) {
        progressEl.style.stroke = '#dc3545';
    } else if (seconds <= 10) {
        progressEl.style.stroke = '#ffc107';
    } else {
        progressEl.style.stroke = '#20c997';
    }
}

function updateScores(scores) {
    const list = elements.scoresList;
    if (!list) return;
    list.innerHTML = '';
    if (!scores || Object.keys(scores).length === 0) {
        list.innerHTML = '<li class="list-group-item text-muted">Нет данных</li>';
        return;
    }
    Object.entries(scores).forEach(([name, score]) => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
            ${name}
            <span class="badge bg-primary rounded-pill">${score}</span>
        `;
        list.appendChild(li);
    });
}

function renderMyWords() {
    const list = elements.myWordsList;
    if (!list) return;
    list.innerHTML = '';
    if (myWords.length === 0) {
        list.innerHTML = '<li class="list-group-item text-muted">Пока ничего</li>';
        return;
    }
    myWords.forEach(word => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
            ${word}
            <span class="badge bg-success rounded-pill">✓</span>
        `;
        list.appendChild(li);
    });
}

function endGame(data) {
    stopTimer();
    setState('lobby');
    if (elements.roomBadge) {
        elements.roomBadge.style.display = 'none';
    }
    if (data.winner) {
        showResultsModal(data);
    }
    fetchLeaderboard();
    if (data.rating !== undefined && elements.ratingDisplay) {
        elements.ratingDisplay.textContent = '⭐ ' + data.rating;
    }
    if (data.rank && elements.rankDisplay) {
        elements.rankDisplay.textContent = data.rank;
    }
    showStatus('Игра окончена! Победитель: ' + data.winner, 'info');
}

function showResultsModal(data) {
    const modal = elements.modal;
    if (!modal) return;
    if (elements.modalTitle) {
        elements.modalTitle.textContent = '🏆 Победитель: ' + data.winner;
    }
    let html = '';
    if (data.results) {
        data.results.forEach(player => {
            html += `
                <div class="mb-2 p-2 bg-dark rounded">
                    <div class="d-flex justify-content-between">
                        <strong>${player.name}</strong>
                        <span class="badge bg-primary">${player.score} очков</span>
                    </div>
                    ${player.words && player.words.length > 0 ? 
                        '<div class="mt-1"><small class="text-muted">Слова: ' + player.words.join(', ') + '</small></div>' : 
                        '<div class="mt-1"><small class="text-muted">Нет слов</small></div>'}
                </div>
            `;
        });
    }
    if (elements.modalBody) {
        elements.modalBody.innerHTML = html || '<p>Результаты игры</p>';
    }
    if (typeof bootstrap !== 'undefined') {
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
    } else {
        modal.style.display = 'block';
    }
}

function hideModal() {
    const modal = elements.modal;
    if (!modal) return;
    if (typeof bootstrap !== 'undefined') {
        const modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) {
            modalInstance.hide();
        }
    } else {
        modal.style.display = 'none';
    }
}

async function fetchHistory() {
    try {
        const response = await fetch('/api/history/' + currentUser.user_id);
        const history = await response.json();
        showHistoryModal(history);
    } catch (e) {
        console.error('Ошибка загрузки истории:', e);
        showStatus('Не удалось загрузить историю игр', 'danger');
    }
}

function showHistoryModal(history) {
    const modal = elements.modal;
    if (!modal) return;
    
    if (elements.modalTitle) {
        elements.modalTitle.textContent = '📜 История игр';
    }
    
    let html = '';
    if (history && history.length > 0) {
        history.forEach(game => {
            const date = new Date(game.started_at).toLocaleDateString('ru-RU');
            const time = new Date(game.started_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            const isWinner = game.is_winner === 1;
            const change = game.rating_change || 0;
            const changeText = change > 0 ? `+${change}` : change;
            const changeColor = change > 0 ? 'text-success' : change < 0 ? 'text-danger' : 'text-muted';
            
            html += `
                <div class="mb-2 p-2 bg-dark rounded">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${date} ${time}</strong>
                            <span class="badge ${isWinner ? 'bg-success' : 'bg-secondary'} ms-2">
                                ${isWinner ? '🏆 Победа' : '❌ Поражение'}
                            </span>
                        </div>
                        <div>
                            <span class="badge bg-primary">${game.score} очков</span>
                            <span class="badge ${changeColor}">${changeText}</span>
                        </div>
                    </div>
                </div>
            `;
        });
    } else {
        html = '<p class="text-muted">У вас пока нет сыгранных игр</p>';
    }
    
    if (elements.modalBody) {
        elements.modalBody.innerHTML = html;
    }
    
    if (typeof bootstrap !== 'undefined') {
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
    } else {
        modal.style.display = 'block';
    }
}

async function fetchRanks() {
    try {
        const response = await fetch('/api/ranks');
        const ranks = await response.json();
        showRanksModal(ranks);
    } catch (e) {
        console.error('Ошибка загрузки рангов:', e);
        showStatus('Не удалось загрузить таблицу рангов', 'danger');
    }
}

function showRanksModal(ranks) {
    const modal = elements.modal;
    if (!modal) return;
    
    if (elements.modalTitle) {
        elements.modalTitle.textContent = '🏅 Таблица рангов';
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-dark table-hover">
                <thead>
                    <tr>
                        <th>Ранг</th>
                        <th>Минимальный рейтинг</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    ranks.sort((a, b) => b.min_rating - a.min_rating);
    
    ranks.forEach(rank => {
        const isCurrent = currentUser && rank.rank === currentUser.rank;
        html += `
            <tr class="${isCurrent ? 'table-active' : ''}">
                <td>
                    ${rank.rank}
                    ${isCurrent ? ' <span class="badge bg-success">Ваш ранг</span>' : ''}
                </td>
                <td>
                    ${rank.min_rating === 0 ? '0+' : rank.min_rating + '+'}
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    if (elements.modalBody) {
        elements.modalBody.innerHTML = html;
    }
    
    if (typeof bootstrap !== 'undefined') {
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
    } else {
        modal.style.display = 'block';
    }
}

function login() {
    const username = elements.username ? elements.username.value.trim() : '';
    const password = elements.password ? elements.password.value.trim() : '';
    
    if (!username || !password) {
        showStatus('Заполните все поля', 'danger');
        return;
    }
    
    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            currentUser = data;
            localStorage.setItem('username', username);
            if (!socket.connected) {
                socket.connect();
            }
            socket.emit('login', { username: username });
        } else {
            showStatus('Ошибка: ' + data.error, 'danger');
        }
    })
    .catch(err => {
        showStatus('Ошибка соединения', 'danger');
    });
}

function register() {
    const username = elements.username ? elements.username.value.trim() : '';
    const password = elements.password ? elements.password.value.trim() : '';
    
    if (!username || !password) {
        showStatus('Заполните все поля', 'danger');
        return;
    }
    
    fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showStatus('Регистрация успешна! Теперь войдите.', 'success');
            if (elements.password) {
                elements.password.value = '';
            }
        } else {
            showStatus('Ошибка: ' + data.error, 'danger');
        }
    })
    .catch(err => {
        showStatus('Ошибка соединения', 'danger');
    });
}

function logout() {
    fetch('/api/logout', { method: 'POST' })
    .then(() => {
        socket.disconnect();
        currentUser = null;
        currentRoom = null;
        isOwner = false;
        inMatchmaking = false;
        if (elements.matchmakingStatus) {
            elements.matchmakingStatus.style.display = 'none';
        }
        showApp(false);
        if (elements.username) {
            elements.username.value = '';
        }
        if (elements.password) {
            elements.password.value = '';
        }
        localStorage.removeItem('username');
        showStatus('Вы вышли из системы', 'info');
    })
    .catch(err => {
        console.error('Ошибка выхода:', err);
    });
}

function createRoom() {
    if (currentUser) {
        socket.emit('create_room', {});
    }
}

function joinRoom() {
    if (elements.joinInput) {
        elements.joinInput.style.display = 'flex';
    }
}

function confirmJoin() {
    const codeInput = document.getElementById('room-code-input');
    const code = codeInput ? codeInput.value.trim().toUpperCase() : '';
    if (code) {
        socket.emit('join_room', { room: code });
        if (elements.joinInput) {
            elements.joinInput.style.display = 'none';
        }
        if (codeInput) {
            codeInput.value = '';
        }
    }
}

function cancelJoin() {
    if (elements.joinInput) {
        elements.joinInput.style.display = 'none';
    }
    const codeInput = document.getElementById('room-code-input');
    if (codeInput) {
        codeInput.value = '';
    }
}

function quickPlay() {
    if (currentUser && !inMatchmaking) {
        socket.emit('quick_play', {});
    } else if (inMatchmaking) {
        showStatus('Вы уже в поиске игры', 'warning');
    }
}

function cancelMatchmaking() {
    if (inMatchmaking) {
        socket.emit('leave_matchmaking', {});
        inMatchmaking = false;
        if (elements.matchmakingStatus) {
            elements.matchmakingStatus.style.display = 'none';
        }
        showStatus('Поиск отменён', 'info');
    }
}

function startGameBtn() {
    if (currentRoom) {
        socket.emit('start_game', { room: currentRoom });
    }
}

function leaveRoom() {
    if (currentRoom) {
        socket.emit('leave_room', { room: currentRoom });
        leaveRoomCleanup();
    }
}

function submitWord() {
    if (gameState !== 'playing' || !timerInterval) {
        showStatus('Игра не активна', 'danger');
        return;
    }
    const word = elements.currentWord ? elements.currentWord.textContent : '';
    if (!word || word === '—' || word.length < 3) {
        showStatus('Слово должно быть минимум 3 буквы', 'danger');
        return;
    }
    socket.emit('submit_word', { room: currentRoom, word: word });
    clearSelection();
}

document.addEventListener('DOMContentLoaded', () => {
    if (elements.loginBtn) elements.loginBtn.addEventListener('click', login);
    if (elements.registerBtn) elements.registerBtn.addEventListener('click', register);
    if (elements.logoutBtn) elements.logoutBtn.addEventListener('click', logout);
    if (elements.createRoomBtn) elements.createRoomBtn.addEventListener('click', createRoom);
    if (elements.joinRoomBtn) elements.joinRoomBtn.addEventListener('click', joinRoom);
    if (elements.joinConfirmBtn) elements.joinConfirmBtn.addEventListener('click', confirmJoin);
    if (elements.joinCancelBtn) elements.joinCancelBtn.addEventListener('click', cancelJoin);
    if (elements.quickPlayBtn) elements.quickPlayBtn.addEventListener('click', quickPlay);
    if (elements.cancelMatchmakingBtn) elements.cancelMatchmakingBtn.addEventListener('click', cancelMatchmaking);
    if (elements.startBtn) elements.startBtn.addEventListener('click', startGameBtn);
    if (elements.leaveRoomBtn) elements.leaveRoomBtn.addEventListener('click', leaveRoom);
    if (elements.submitBtn) elements.submitBtn.addEventListener('click', submitWord);
    if (elements.clearBtn) elements.clearBtn.addEventListener('click', clearSelection);
    if (elements.modalClose) elements.modalClose.addEventListener('click', hideModal);
    if (elements.modalActionBtn) elements.modalActionBtn.addEventListener('click', hideModal);
    
    if (elements.username) {
        elements.username.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && elements.password) {
                elements.password.focus();
            }
        });
    }
    if (elements.password) {
        elements.password.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') login();
        });
    }
    
    const roomCodeInput = document.getElementById('room-code-input');
    if (roomCodeInput) {
        roomCodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') confirmJoin();
        });
    }
    
    if (elements.modal) {
        elements.modal.addEventListener('hidden.bs.modal', () => {
            if (gameState === 'lobby') {
                setState('lobby');
            }
        });
    }
    
    console.log('🧬 LetterMutant клиент загружен');
});
