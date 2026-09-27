export const API_BASE_URL = (import.meta.env.VITE_MEAL_API_URL || "/api/meal-planner").replace(/\/$/, "");

export async function authFetch(input, options = {}) {
  const url = /^https?:\/\//.test(input) || input.startsWith(API_BASE_URL)
    ? input
    : `${API_BASE_URL}${input.startsWith("/") ? "" : "/"}${input}`;
  const headers = new Headers(options.headers || {});
  const careToken = localStorage.getItem("access_token");
  if (careToken) headers.set("Authorization", `Bearer ${careToken}`);

  return fetch(url, { ...options, headers });
}

export async function createCareConnectMealSession() {
  const careToken = localStorage.getItem("access_token");
  if (!careToken) throw new Error("CareConnect login is required");
  const response = await authFetch(`${API_BASE_URL}/careconnect/session`, {
    method: "POST",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Unable to start Meal Planner");
  return data;
}

export default authFetch;
