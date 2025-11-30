document.addEventListener('DOMContentLoaded', function() {
    const socket = io();

    // Основные элементы DOM
    const messages = document.getElementById('messages');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const onlineUsers = document.getElementById('online-users');
    
    const privateChat = document.getElementById('private-chat');
    const privateMessages = document.getElementById('private-messages');
    const privateForm = document.getElementById('private-form');
    const privateInput = document.getElementById('private-input');
    const privateUser = document.getElementById('private-user');
    const closePrivate = document.getElementById('close-private');

    let activePrivateUser = null;
    let userMap = {}; // Сопоставление username → user_id (заполняется при загрузке)

    // Инициализация: получаем список пользователей с их ID
    fetch('/api/users')
        .then(response => response.json())
        .then(data => {
            userMap = data.reduce((map, user) => {
                map[user.username] = user.id;
                return map;
            }, {});
        });

    // Отправка общего сообщения
    messageForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (messageInput.value.trim()) {
            socket.emit('send_message', {
                content: messageInput.value,
                receiver_id: null  // общий чат
            });
            messageInput.value = '';
        }
    });

    // Получение сообщений
    socket.on('new_message', function(data) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message';
        
        let sender = data.sender;
        if (data.receiver_id) {
            sender += ' → Вам';
        }
        
        messageDiv.innerHTML = `
            <strong>${sender}:</strong>
            ${data.content}
            <small>${data.timestamp.split('T')[1].substring(0, 5)}</small>
        `;
        
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
        
        // Если это приватное сообщение для текущего пользователя
        if (data.receiver_id === current_user_id) {
            showPrivateMessage(data.sender, data.content, data.timestamp);
        }
    });

    // Обновление списка онлайн-пользователей
    socket.on('online_users', function(users) {
        onlineUsers.innerHTML = '';
        users.forEach(user => {
            const li = document.createElement('li');
            li.textContent = user;
            
            // Клик по пользователю для приватного чата
            li.addEventListener('click', () => {
                activePrivateUser = user;
                privateUser.textContent = user;
                privateChat.style.display = 'block';
                // Очищаем историю приватных сообщений при смене пользователя
                privateMessages.innerHTML = '';
            });
            
            onlineUsers.appendChild(li);
        });
    });

    // Уведомления о присоединении/выходе
    socket.on('user_joined', function(data) {
        flashMessage(`${data.username} присоединился к чату`, 'info');
    });

    socket.on('user_left', function(data) {
        flashMessage(`${data.username} покинул чат`, 'warning');
    });

    // Обработчик клика по онлайн-пользователям
    onlineUsers.addEventListener('click', (e) => {
        if (e.target.tagName === 'LI') {
            const username = e.target.textContent.split('Онлайн')[0].trim();
            const userId = parseInt(e.target.dataset.userId);
            
            // Запрет открытия чата с самим собой
            if (userId === currentUserId) {
                alert('Нельзя открыть чат с самим собой!');
                return;
            }
            
            openPrivateChat(userId, username);
        }
    });

    // Приватные сообщения
    privateForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (privateInput.value.trim() && activePrivateUser) {
            const receiverId = userMap[activePrivateUser];
            if (receiverId) {
                socket.emit('send_message', {
                    content: privateInput.value,
                    receiver_id: receiverId
                });
                showPrivateMessage(`Вы → ${activePrivateUser}`, privateInput.value);
                privateInput.value = '';
            } else {
                flashMessage('Не удалось определить ID пользователя', 'error');
            }
        }
    });

    closePrivate.addEventListener('click', function() {
        privateChat.style.display = 'none';
        activePrivateUser = null;
    });

    // Вспомогательные функции
    function flashMessage(text, type) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = text;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 3000);
    }

    function sendPrivateMessage(userId, input) {
        if (input.value.trim() === '') return;


        // Запрет отправки сообщений самому себе
        if (userId === currentUserId) {
            alert('Нельзя отправить сообщение самому себе!');
            input.value = '';
            return;
        }

        socket.emit('send_private_message', {
            receiver_id: userId,
            content: input.value
        });
        input.value = '';
    }

    function showPrivateMessage(sender, content, timestamp = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'private-message';
        
        const timeStr = timestamp 
            ? timestamp.split('T')[1].substring(0, 5)
            : new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        
        msgDiv.innerHTML = `
            <strong>${sender}:</strong> 
            ${content}
            <small>${timeStr}</small>
        `;
        
        privateMessages.appendChild(msgDiv);
        privateMessages.scrollTop = privateMessages.scrollHeight;
    }
});
