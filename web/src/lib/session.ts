import { randomId } from "@/lib/utils";

const SESSION_KEY = "royal.chatSession";
const TOKEN_KEY = "royal.dashboardToken";
const DEMO_KEY = "royal.demoMode";

function read(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    return;
  }
}

export function getSessionId() {
  const existing = read(SESSION_KEY);
  if (existing && /^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing;
  return resetSessionId();
}

export function resetSessionId() {
  const fresh = randomId(24);
  write(SESSION_KEY, fresh);
  return fresh;
}

export function getToken() {
  return read(TOKEN_KEY);
}

export function setToken(token: string | null) {
  write(TOKEN_KEY, token);
}

export function getDemoMode() {
  return read(DEMO_KEY) !== "off";
}

export function setDemoMode(enabled: boolean) {
  write(DEMO_KEY, enabled ? "on" : "off");
}
