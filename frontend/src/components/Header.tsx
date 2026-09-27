/**
 * Header Component - Project navigation and user menu
 */

import React from 'react';
import { cn } from '../lib/utils';

interface HeaderProps {
  project: {
    id: string;
    name: string;
    created_at: string;
  };
  className?: string;
}

export function Header({ project, className }: HeaderProps): JSX.Element {
  return (
    <header className={cn(
      "flex items-center justify-between px-4 py-2 bg-gray-900/50 border-b border-gray-800",
      className
    )}>
      {/* Left: Project */}
      <div className="flex items-center space-x-4">
        <h1 className="text-lg font-semibold text-gray-100">
          RANN
        </h1>
        <div className="text-sm text-gray-400">
          <span className="text-gray-500">/</span>
          <span className="text-gray-300 font-medium">{project.name}</span>
        </div>
      </div>

      {/* Middle: Status */}
      <div className="text-sm text-gray-400">
        Status: Active
      </div>

      {/* Right: Account Menu */}
      <div className="flex items-center space-x-4">
        <button className="px-3 py-1 text-sm text-gray-300 hover:text-gray-100 rounded hover:bg-gray-800">
          Settings
        </button>
        <button className="px-3 py-1 text-sm text-gray-300 hover:text-gray-100 rounded hover:bg-gray-800">
          Account
        </button>
      </div>
    </header>
  );
}