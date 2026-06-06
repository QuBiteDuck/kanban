const API_BASE = '/api';

export const api = {
    async request(url, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            credentials: 'include', // Важно для HttpOnly cookies
            ...options,
        };

        try {
            const response = await fetch(`${API_BASE}${url}`, config);
            
            if (response.status === 401) {
                window.location.href = '/login.html';
                throw new Error('Unauthorized');
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Произошла ошибка при запросе');
            }

            // Если ответ пустой (например, 204 No Content или успешное удаление)
            if (response.status === 204) return null;

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    get(url) { return this.request(url); },
    post(url, body) { return this.request(url, { method: 'POST', body: JSON.stringify(body) }); },
    put(url, body) { return this.request(url, { method: 'PUT', body: JSON.stringify(body) }); },
    patch(url, body) { return this.request(url, { method: 'PATCH', body: JSON.stringify(body) }); },
    delete(url) { return this.request(url, { method: 'DELETE' }); },
};