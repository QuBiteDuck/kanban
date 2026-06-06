import { checkAuth } from "./api/auth.js";
import { storage } from "./utils/storage.js";

document.addEventListener("DOMContentLoaded", () => {
  checkAuth();
  updateSidebar();
});

function updateSidebar() {
  const user = storage.getCurrentUser();
  if (!user) return;
  const nameEl = document.querySelector(".user-info .name");
  const roleEl = document.querySelector(".user-info .roles");
  if (nameEl) nameEl.textContent = user.name;
  if (roleEl)
    roleEl.textContent = user.role === "admin" ? "Администратор" : "Наставник";
}

// В highlightNav() или отдельной функции
function setupSmartBoardLink() {
  const lastBoardId = localStorage.getItem("imctech_last_board_id");
  const boardLink = document.querySelector(
    '.nav-item a[href="dashboard.html"]',
  ); // или найди по тексту "Доска"

  if (boardLink && lastBoardId) {
    boardLink.href = `mainboard.html?boardId=${lastBoardId}`;
  }
}
