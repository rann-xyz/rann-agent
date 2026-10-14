/**
 * Auth Context - Authentication state management for RANN Web IDE
 */

import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { AuthAPI, type Project } from '../services/api';

interface User {
  id: string;
  email: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  projects: Project[];
  currentProject: Project | null;
  setCurrentProject: (project: Project | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);

  // Check auth status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  // Load projects when user changes
  useEffect(() => {
    if (user) {
      loadProjects();
    }
  }, [user]);

  async function checkAuth() {
    try {
      const userData = await AuthAPI.me();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadProjects() {
    try {
      const projectList = await ProjectAPI.list();
      setProjects(projectList);
    } catch (err) {
      console.error('Failed to load projects:', err);
      setProjects([]);
    }
  }

  async function login(email: string, password: string) {
    setError(null);
    try {
      await AuthAPI.login(email, password);
      await checkAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
      throw err;
    }
  }

  async function register(email: string, password: string) {
    setError(null);
    try {
      await AuthAPI.register(email, password);
      await checkAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
      throw err;
    }
  }

  async function logout() {
    try {
      await AuthAPI.logout();
    } catch {
      // Ignore logout errors
    }
    setUser(null);
    setProjects([]);
    setCurrentProject(null);
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      error,
      login,
      register,
      logout,
      projects,
      currentProject,
      setCurrentProject,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}

// Import ProjectAPI for use in this file
import { ProjectAPI } from '../services/api';