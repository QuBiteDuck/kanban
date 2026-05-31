import { storage } from "../utils/storage.js";

export async function login(email, password) {
  const user = storage
    .getUsers()
    .find((u) => u.email === email && u.password === password);
  if (user) {
    storage.setCurrentUser(user);
    return { success: true };
  }
  return { success: false, error: "Неверный email или пароль" };
}

export async function register(data) {
  if (storage.getUsers().find((u) => u.email === data.email)) {
    return { success: false, error: "Email уже занят" };
  }
  const newUser = { id: Date.now(), ...data, role: "student" };
  storage.saveUsers([...storage.getUsers(), newUser]);
  storage.setCurrentUser(newUser);
  return { success: true };
}

export function checkAuth() {
  const user = storage.getCurrentUser();
  const path = window.location.pathname;
  const isAuth = path.includes("login.html") || path.includes("register.html");

  if (!user && !isAuth) window.location.href = "login.html";
  if (user && isAuth) window.location.href = "dashboard.html";
}
