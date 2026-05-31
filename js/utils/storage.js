export const storage = {
  getUsers: () => JSON.parse(localStorage.getItem("imctech_users") || "[]"),
  saveUsers: (users) =>
    localStorage.setItem("imctech_users", JSON.stringify(users)),
  getCurrentUser: () =>
    JSON.parse(localStorage.getItem("imctech_current_user")),
  setCurrentUser: (user) =>
    localStorage.setItem("imctech_current_user", JSON.stringify(user)),
  clearCurrentUser: () => localStorage.removeItem("imctech_current_user"),
};
