import { useState } from "react";
import { User } from "lucide-react";

const SIZES = {
  sm: { img: "h-6 w-6", icon: "h-6 w-6 p-0.5" },
  md: { img: "h-8 w-8", icon: "h-8 w-8 p-1" },
  lg: { img: "h-16 w-16", icon: "h-16 w-16 p-3" },
} as const;

interface UserAvatarProps {
  url: string | null | undefined;
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}

export function UserAvatar({
  url,
  name,
  size = "md",
  className = "",
}: UserAvatarProps) {
  const [failed, setFailed] = useState(false);
  const s = SIZES[size];

  if (!url || failed) {
    return (
      <User
        data-testid="avatar-fallback"
        className={`${s.icon} rounded-full bg-gray-200 dark:bg-gray-700 ${className}`}
      />
    );
  }

  return (
    <img
      src={url}
      alt={name}
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`${s.img} rounded-full ${className}`}
    />
  );
}
