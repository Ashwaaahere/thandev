'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { thandevFetchJSON } from '@/lib/thandevApi';

type NotificationListItem = {
  id: string;
  type: string;
  title: string;
  message: string | null;
  link_url: string | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
};

type NotificationListResponse = {
  items: NotificationListItem[];
  total: number;
};

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return 'just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return date.toLocaleDateString();
  }
}

export default function NotificationBell() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const [notifications, setNotifications] = useState<NotificationListItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadNotifications = useCallback(async () => {
    if (sessionStatus !== 'authenticated' || !session) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await thandevFetchJSON<NotificationListResponse>(
        '/api/notifications?limit=10',
        session
      );
      setNotifications(res.items ?? []);
    } catch (e) {
      console.error('Failed to load notifications', e);
      setError('Failed to load notifications');
    } finally {
      setIsLoading(false);
    }
  }, [session, sessionStatus]);

  const markAsRead = useCallback(async (id: string) => {
    if (!session) return;
    
    try {
      await thandevFetchJSON(`/api/notifications/${id}/read`, session, { method: 'POST' });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    } catch (e) {
      console.error('Failed to mark notification as read', e);
    }
  }, [session]);

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 30000);
    pollIntervalRef.current = interval;
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [loadNotifications]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-[var(--surface-2)] transition-colors"
        aria-label="Notifications"
      >
        <svg className="w-6 h-6" style={{ color: 'var(--fg)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 h-5 w-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          <div className="p-4 border-b border-[var(--border)]">
            <h3 className="font-semibold text-[var(--fg)]">Notifications</h3>
          </div>
          {isLoading ? (
            <div className="p-4 text-center text-[var(--muted)]">Loading...</div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">{error}</div>
          ) : notifications.length === 0 ? (
            <div className="p-4 text-center text-[var(--muted)]">No notifications</div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  onClick={() => {
                    if (notification.link_url) {
                      router.push(notification.link_url);
                    }
                    if (!notification.is_read) {
                      markAsRead(notification.id);
                    }
                    setIsOpen(false);
                  }}
                  className="w-full p-4 text-left hover:bg-[var(--surface-2)] transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-sm text-[var(--fg)]">
                        {notification.title}
                      </p>
                      {notification.message && (
                        <p className="text-xs mt-1 line-clamp-1" style={{ color: 'var(--muted)' }}>
                          {notification.message}
                        </p>
                      )}
                      <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                        {formatRelativeTime(notification.created_at)}
                      </p>
                    </div>
                    {!notification.is_read && (
                      <span className="h-2 w-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0"></span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
