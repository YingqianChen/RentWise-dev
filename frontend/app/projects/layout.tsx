"use client";

import { useEffect, type ReactNode } from "react";
import { AUTH_CHANGED_EVENT, getToken, TOKEN_KEY } from "@/lib/auth";

export default function ProjectsLayout({ children }: { children: ReactNode }) {
  useEffect(() => {
    const initialToken = getToken();
    const syncSession = () => {
      const token = getToken();
      if (!token || token !== initialToken) {
        // Discard private page state on logout or account changes in another tab.
        window.location.replace(token ? "/projects" : "/login");
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === TOKEN_KEY || event.key === null) syncSession();
    };
    syncSession();
    window.addEventListener("storage", onStorage);
    window.addEventListener(AUTH_CHANGED_EVENT, syncSession);
    window.addEventListener("pageshow", syncSession);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(AUTH_CHANGED_EVENT, syncSession);
      window.removeEventListener("pageshow", syncSession);
    };
  }, []);
  return children;
}
