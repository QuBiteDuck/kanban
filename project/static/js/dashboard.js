import { api } from './api.js';

document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.querySelector('.boards-grid');
    if (!grid) return;

    grid.innerHTML = '<p>Загрузка...</p>';

    try {
        const data = await api.get('/boards?page=1&limit=50');
        grid.innerHTML = ''; // Очищаем заглушку

        if (data.items.length === 0) {
            window.location.href = '/welcome.html';
            return;
        }

        data.items.forEach(board => {
            const card = document.createElement('article');
            card.className = 'board-card';
            card.onclick = () => window.location.href = `/mainboard.html?board_id=${board.id}`;
            
            card.innerHTML = `
                <div class="card-header">
                    <div class="card-icon">IM</div>
                </div>
                <div>
                    <h3 class="card-title">${board.name}</h3>
                    <p class="card-desc">${board.description || 'Нет описания'}</p>
                </div>
                <div class="card-footer">
                    <span class="time">ID: ${board.id}</span>
                </div>
            `;
            grid.appendChild(card);
        });

        // Кнопка создания новой
        const addBtn = document.createElement('button');
        addBtn.className = 'board-card create-new';
        addBtn.onclick = () => window.location.href = '/welcome.html';
        addBtn.innerHTML = `
            <div class="create-icon">+</div>
            <span class="create-text">Создать новую доску</span>
        `;
        grid.appendChild(addBtn);

    } catch (err) {
        grid.innerHTML = `<p style="color:red">Ошибка загрузки: ${err.message}</p>`;
    }
});