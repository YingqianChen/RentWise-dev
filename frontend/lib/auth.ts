/**
 * Authentication utilities for client-side auth
 */

export const AUTH_CHANGED_EVENT = "rentwise-auth-changed";
export const TOKEN_KEY = "rentwise_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function clearToken(expectedToken?: string): boolean {
  if (typeof window === "undefined") return false;
  // A late response from an older session must never clear a newer login.
  if (expectedToken !== undefined && getToken() !== expectedToken) return false;
  localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  return true;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
