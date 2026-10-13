/**
 * Auth Guard Component - Redirects unauthenticated users to login
 */

import React from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from './AuthContext';

export function AuthGuard({ children }: { children: React.ReactNode }): JSX.Element {
  const router = useRouter();
  const { user, loading } = useAuth();

  React.useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-gray-400">Redirecting to login...</div>
      </div>
    );
  }

  return <>{children}</>;
}