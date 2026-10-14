/**
 * Terminal Workspace - Main RANN Web IDE layout
 * 
 * Layout:
 * ┌─────────────────────────────────────────────────────────────┐
 * │ RANN                     project     status     account  │
 * ├────────────┬──────────────────────────────────┬──────────┤
 * │            │                                  │          │
 * │ FILE       │             EDITOR               │  AGENT   │
 * │ EXPLORER   │                                  │          │
 * │            │                                  │          │
 * ├────────────┴──────────────────────────────────┴──────────┤
 * │ TERMINAL                                                   │
 * │ $                                                           │
 * └─────────────────────────────────────────────────────────────┘
 */

import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { FileExplorer } from '../components/FileExplorer';
import { Editor } from '../components/Editor';
import { AgentPanel } from '../components/AgentPanel';
import { TerminalComponent } from '../components/Terminal';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { AuthGuard } from '../contexts/AuthGuard';
import { ProjectAPI } from '../services/api';

function WorkspaceContent(): JSX.Element {
  const { currentProject, setCurrentProject, projects } = useAuth();
  const [activeView, setActiveView] = useState<'files' | 'editor' | 'agent'>('editor');
  const [activeFile, setActiveFile] = useState<string | null>(null);

  // Auto-select first project if none selected
  useEffect(() => {
    if (!currentProject && projects.length > 0) {
      setCurrentProject(projects[0]);
    }
  }, [projects, currentProject, setCurrentProject]);

  if (!currentProject) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl text-gray-400 mb-4">No project selected</h2>
          <p className="text-gray-600">Select or create a project to begin</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      <Header project={currentProject} />

      <div className="flex flex-1 overflow-hidden">
        {/* File Explorer Sidebar */}
        <FileExplorer 
          className="w-64 flex-shrink-0 border-r border-gray-800"
          onFileSelect={setActiveFile}
          projectId={currentProject.id}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* View Tabs */}
          <div className="flex border-b border-gray-800 bg-gray-900/50">
            <button
              onClick={() => setActiveView('editor')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeView === 'editor' 
                  ? 'border-b-2 border-blue-500 text-blue-400' 
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Editor
            </button>
            <button
              onClick={() => setActiveView('agent')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeView === 'agent' 
                  ? 'border-b-2 border-blue-500 text-blue-400' 
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Agent
            </button>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-hidden">
            {activeView === 'editor' && (
              <Editor 
                filePath={activeFile}
                projectId={currentProject.id}
                className="h-full"
              />
            )}
            {activeView === 'agent' && (
              <AgentPanel projectId={currentProject.id} />
            )}
          </div>
        </div>
      </div>

      {/* Terminal at Bottom */}
      <div className="border-t border-gray-800">
        <TerminalComponent 
          sessionId={currentProject.id}
          projectId={currentProject.id}
          userId={currentProject.owner_id}
        />
      </div>
    </div>
  );
}

export function TerminalWorkspace(): JSX.Element {
  return (
    <AuthProvider>
      <WorkspaceContent />
    </AuthProvider>
  );
}