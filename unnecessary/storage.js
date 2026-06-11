// ✅ ПРАВИЛЬНО: именованный экспорт объекта
export const storage = {
  getUsers: () => JSON.parse(localStorage.getItem("imctech_users") || "[]"),
  saveUsers: (users) =>
    localStorage.setItem("imctech_users", JSON.stringify(users)),
  getCurrentUser: () =>
    JSON.parse(localStorage.getItem("imctech_current_user")),
  setCurrentUser: (user) =>
    localStorage.setItem("imctech_current_user", JSON.stringify(user)),
  clearCurrentUser: () => localStorage.removeItem("imctech_current_user"),

  getTasks: () => JSON.parse(localStorage.getItem("imctech_tasks") || "[]"),
  saveTasks: (tasks) =>
    localStorage.setItem("imctech_tasks", JSON.stringify(tasks)),

  getBoards: () => JSON.parse(localStorage.getItem("imctech_boards") || "[]"),
  saveBoards: (boards) =>
    localStorage.setItem("imctech_boards", JSON.stringify(boards)),
  createBoard: (board) => {
    const boards = storage.getBoards();
    boards.push(board);
    storage.saveBoards(boards);
  },
};
