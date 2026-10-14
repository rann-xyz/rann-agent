/**
 * Header Component - Project navigation and user menu
 */

import React, { useState } from 'react';
import { cn } from '../lib/utils';
import { useAuth } from '../contexts/AuthContext';

interface HeaderProps {
  project: {
    id: string;
    name: string;
    created_at: string;
  };
}

export function Header({ project }: HeaderProps): JSX.Element {
  const { projects, currentProject, setCurrentProject, logout } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  const handleCreateProject = async () => {
    try {
      const newProject = await import('../services/api').then(m => m.ProjectAPI.create('New Project'));
      setCurrentProject(newProject);
    } catch (err) {
      console.error('Failed to create project:', err);
    }
  };

  return (
    <header className={cn(
      "flex items-center justify-between px-4 py-2 bg-gray-900/50 border-b border-gray-800",
    )}>
      {/* Left: Project */}
      <div className="flex items-center space-x-4">
        <h1 className="text-lg font-semibold text-gray-100">
          RANN
        </h1>
        <div className="relative">
          <select
            value={project?.id || ''}
            onChange={(e) => {
              const proj = projects.find(p => p.id === e.target.value);
              if (proj) setCurrentProject(proj);
            }}
            className="bg-gray-800 text-gray-300 text-sm rounded px-2 py-1 pr-8 appearance-none"
          >
            {projects.map(p => (
              <option key={p.id} value={p.id} className="bg-gray-800">
                {p.name}
              </option>
            ))}
          </select>
          {/* + icon overlay */}
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
            ▼
          </span>
        </div>
        <button
          onClick={handleCreateProject}
          className="text-xs text-gray-400 hover:text-gray-200 underline"
        >
          New Project
        </button>
      </div>

      {/* Middle: Status */}
      <div className="text-sm text-gray-400">
        Status: Active
      </div>

      {/* Right: Account Menu */}
      <div className="relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="px-3 py-1 text-sm text-gray-300 hover:text-gray-100 rounded hover:bg-gray-800"
        >
          Account
        </button>
        {showMenu && (
          <div className="absolute right-0 mt-2 w-48 bg-gray-800 border border-gray-700 rounded shadow-lg z-10">
            <button
              onClick={logout}
              className="w-full px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 text-left"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}