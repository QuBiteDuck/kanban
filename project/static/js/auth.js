import { api } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    
    // Проверка: если мы уже залогинены и пытаемся зайти на login/register -> редирект на dashboard
    if (path.includes('login.html') || path.includes('register.html')) {
        checkAuthAndRedirect();
    }

    // Логика формы входа
    const loginForm = document.querySelector('.login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.querySelector('input[type="email"]').value;
            const password = document.querySelector('input[type="password"]').value;
            
            try {
                await api.post('/auth/login', { email, password });
                window.location.href = '/dashboard.html';
            } catch (err) {
                alert(err.message);
            }
        });
    }

    // Логика формы регистрации
    const registerForm = document.querySelector('.auth-form');
    if (registerForm && path.includes('register.html')) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const inputs = registerForm.querySelectorAll('input');
            const name = inputs[0].value;
            const email = inputs[1].value;
            const password = inputs[2].value;

            try {
                await api.post('/auth/register', { name, email, password });
                // После регистрации сразу логинимся
                await api.post('/auth/login', { email, password });
                window.location.href = '/dashboard.html';
            } catch (err) {
                alert(err.message);
            }
        });
    }
});

async function checkAuthAndRedirect() {
    try {
        await api.get('/auth/me');
        // Если запрос прошел успешно, значит пользователь залогинен
        if (!window.location.pathname.includes('dashboard.html') && 
            !window.location.pathname.includes('mainboard.html') &&
            !window.location.pathname.includes('results.html') &&
            !window.location.pathname.includes('settings.html')) {
            window.location.href = '/dashboard.html';
        }
    } catch (e) {
        // Если 401, остаемся на странице логина
    }
}