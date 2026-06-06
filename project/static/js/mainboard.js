import { api } from './api.js';

// Словарь для локализации
const I18N = {
    priorities: { high: 'Высокий', med: 'Средний', low: 'Низкий' },
    columns: { not_started: 'Не начато', in_progress: 'В работе', done: 'Готово' }
};

let currentBoardId = null;

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    currentBoardId = params.get('board_id'); // Ожидаем ?board_id=1 в URL

    if (!currentBoardId) {
        window.location.href = '/dashboard.html';
        return;
    }

    await loadTasks();
    setupDragAndDrop();
    setupAddTaskButtons();
});

async function loadTasks() {
    try {
        // Загружаем все задачи доски (пагинация на бэкенде, но для канбана часто нужно всё)
        // Для простоты берем limit=100
        const data = await api.get(`/boards/${currentBoardId}/tasks?limit=100`);
        renderBoard(data.items);
    } catch (err) {
        console.error('Failed to load tasks', err);
    }
}

function renderBoard(tasks) {
    // Очищаем колонки
    ['not_started', 'in_progress', 'done'].forEach(col => {
        const container = document.querySelector(`.column[data-column="${col}"] .column-body`);
        if (container) {
            // Сохраняем кнопку "Добавить"
            const addBtn = container.querySelector('.add-task-btn');
            container.innerHTML = '';
            if (addBtn) container.appendChild(addBtn);
        }
    });

    tasks.forEach(task => {
        const card = createTaskCard(task);
        const colBody = document.querySelector(`.column[data-column="${task.column}"] .column-body`);
        if (colBody) {
            const addBtn = colBody.querySelector('.add-task-btn');
            addBtn ? colBody.insertBefore(card, addBtn) : colBody.appendChild(card);
        }
    });

    updateCounters();
}

function createTaskCard(task) {
    const div = document.createElement('div');
    div.className = 'task-card';
    div.draggable = true;
    div.dataset.taskId = task.id;
    
    const priorityText = I18N.priorities[task.priority] || task.priority;
    const assigneeInitials = task.assignee ? task.assignee.name?.charAt(0) || 'A' : '?';

    div.innerHTML = `
        <div class="task-tags">
            ${task.tags.map(tag => `<span class="task-tag">${tag}</span>`).join('')}
        </div>
        <div class="task-title">${task.title}</div>
        <div class="task-meta">
            <span class="priority ${task.priority}">${priorityText}</span>
            <span class="due-date">🕒 ${task.due_date || '—'}</span>
        </div>
        <div class="task-footer">
            <div class="task-footer-left">
                ${task.assignee ? `<div class="avatar" style="background:#6366f1;color:white">${assigneeInitials}</div>` : ''}
            </div>
            <span class="task-menu" onclick="event.stopPropagation(); deleteTask(${task.id})">🗑</span>
        </div>
    `;

    div.addEventListener('click', () => {
        window.location.href = `/task-result.html?task_id=${task.id}`;
    });

    div.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', task.id);
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => div.style.opacity = '0.5', 0);
    });

    div.addEventListener('dragend', () => {
        div.style.opacity = '1';
    });

    return div;
}

function setupDragAndDrop() {
    const columns = document.querySelectorAll('.column-body');
    columns.forEach(col => {
        col.addEventListener('dragover', (e) => {
            e.preventDefault();
            col.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
        });

        col.addEventListener('dragleave', () => {
            col.style.backgroundColor = '';
        });

        col.addEventListener('drop', async (e) => {
            e.preventDefault();
            col.style.backgroundColor = '';
            
            const taskId = e.dataTransfer.getData('text/plain');
            const columnEl = col.closest('.column');
            const targetColumn = columnEl.dataset.column;
            
            // Определяем substatus в зависимости от колонки
            let targetSubstatus = null;
            if (targetColumn === 'done') targetSubstatus = 'in_review'; // Если кидаем в Done, считаем что на проверку
            
            try {
                await api.patch(`/tasks/${taskId}/move`, {
                    target_column: targetColumn,
                    target_substatus: targetSubstatus
                });
                loadTasks(); // Перезагружаем доску для актуальности
            } catch (err) {
                alert('Ошибка при перемещении: ' + err.message);
            }
        });
    });
}

async function deleteTask(taskId) {
    if (!confirm('Удалить задачу?')) return;
    try {
        await api.delete(`/tasks/${taskId}`);
        loadTasks();
    } catch (err) {
        alert(err.message);
    }
}

function setupAddTaskButtons() {
    document.querySelectorAll('.add-task-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const column = btn.closest('.column');
            const status = column.dataset.column;
            openTaskModal(status);
        });
    });
}

async function openTaskModal(column) {
    const title = prompt('Название задачи:');
    if (!title) return;
    
    try {
        await api.post(`/boards/${currentBoardId}/tasks`, {
            title,
            priority: 'med',
            column: column
        });
        loadTasks();
    } catch (err) {
        alert(err.message);
    }
}

function updateCounters() {
    // Реализация счетчиков по аналогии с старым кодом, но на основе загруженных данных
    // Можно добавить логику здесь
}