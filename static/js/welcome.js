import { api } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    const createBtn = document.querySelector('.btn-primary');
    if (!createBtn) return;

    createBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        
        const nameInput = document.querySelector('input[type="text"]');
        const descInput = document.querySelector('textarea');
        
        const name = nameInput.value.trim();
        const description = descInput.value.trim();

        if (!name) {
            alert('Введите название доски');
            return;
        }

        try {
            const board = await api.post('/boards', { name, description });
            window.location.href = `/mainboard.html?board_id=${board.id}`;
        } catch (err) {
            alert(err.message);
        }
    });
});