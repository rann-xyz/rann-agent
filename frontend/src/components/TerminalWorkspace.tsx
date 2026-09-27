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

import React, { useState } from 'react';
import { Header } from '../components/Header';
import { FileExplorer } from '../components/FileExplorer';
import { Editor } from '../components/Editor';
import { AgentPanel } from '../components/AgentPanel';
import { TerminalComponent } from '../components/Terminal';

// TODO: These will be replaced with actual API integration
const mockProject = {
  id: 'demo-project',
  name: 'demo-project',
  description: 'RANN Agent Project',
  owner_id: 'user-1',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

export function TerminalWorkspace(): JSX.Element {
  const [activeView, setActiveView] = useState<'files' | 'editor' | 'agent'>('editor');
  const [activeFile, setActiveFile] = useState<string | null>(null);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      <Header project={mockProject} />

      <div className="flex flex-1 overflow-hidden">
        {/* File Explorer Sidebar */}
        <FileExplorer 
          className="w-64 flex-shrink-0 border-r border-gray-800"
          onFileSelect={setActiveFile}
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
                className="h-full"
              />
            )}
            {activeView === 'agent' && (
              <AgentPanel projectId={mockProject.id} />
            )}
          </div>
        </div>
      </div>

      {/* Terminal at Bottom */}
      <div className="border-t border-gray-800">
        <TerminalComponent 
          sessionId={mockProject.id}
          projectId={mockProject.id}
          userId="user-1"
        />
      </div>
    </div>
  );
}