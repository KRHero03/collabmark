/**
 * Reactive hook that tracks whether the app is in dark mode.
 *
 * Watches `document.documentElement.classList` for the "dark" class via
 * MutationObserver, so any component using this hook will re-render
 * immediately when the user toggles the theme in the Navbar.
 */

import { useEffect, useState } from "react";

export function useDarkMode(): boolean {
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  return isDark;
}
