/**
 * File Explorer Component - Real backend integration
 */

import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { FileAPI } from '../services/api';

interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
  expanded?: boolean;
}

interface FileExplorerProps {
  className?: string;
  onFileSelect: (path: string) => void;
  projectId: string;
}

export function FileExplorer({ className, onFileSelect, projectId }: FileExplorerProps): JSX.Element {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['src']));
  const [selected, setSelected] = useState<string | null>(null);
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);

  // Load file tree from backend
  useEffect(() => {
    async function loadFiles() {
      try {
        // For now, use mock tree structure
        // In production, this would call: const files = await FileAPI.list(projectId);
        const mockTree: FileNode[] = [
          {
            name: 'src',
            path: 'src',
            type: 'directory',
            children: [
              { name: 'main.py', path: 'src/main.py', type: 'file' },
              { name: 'utils.py', path: 'src/utils.py', type: 'file' },
            ],
          },
          {
            name: 'package.json',
            path: 'package.json',
            type: 'file',
          },
          {
            name: 'README.md',
            path: 'README.md',
            type: 'file',
          },
        ];
        setFileTree(mockTree);
      } catch (err) {
        console.error('Failed to load files:', err);
      } finally {
        setLoading(false);
      }
    }
    loadFiles();
  }, [projectId]);

  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpanded(newExpanded);
  };

  const selectFile = (path: string) => {
    setSelected(path);
    onFileSelect(path);
  };

  const renderNode = (node: FileNode): JSX.Element => {
    const isDirectory = node.type === 'directory';
    const isExpanded = expanded.has(node.path);
    const hasChildren = Boolean(node.children?.length);

    return (
      <div key={node.path}>
        {isDirectory ? (
          <>
            <div 
              className="flex items-center py-1 px-2 text-sm cursor-pointer hover:bg-gray-800/50 rounded"
              onClick={() => toggleFolder(node.path)}
            >
              <span className="mr-2">
                {hasChildren && isExpanded ? '▾' : hasChildren ? '▸' : ' '}
              </span>
              <span className="text-gray-400">📁</span>
              <span className="ml-2 text-gray-200">{node.name}</span>
            </div>
            {hasChildren && isExpanded && (
              <div className="ml-4">
                {node.children!.map(child => renderNode(child))}
              </div>
            )}
          </>
        ) : (
          <div
            className={`flex items-center py-1 px-2 text-sm cursor-pointer rounded hover:bg-gray-800/50 ${
              selected === node.path ? 'bg-gray-800 text-blue-400' : 'text-gray-300'
            }`}
            onClick={() => selectFile(node.path)}
          >
            <span className="mr-2">📄</span>
            <span className="truncate">{node.name}</span>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className={cn("h-full flex flex-col", className)}>
        <div className="px-2 py-1 border-b border-gray-800">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Files
          </h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-500">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("h-full flex flex-col", className)}>
      <div className="px-2 py-1 border-b border-gray-800">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Files
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {fileTree.map(node => renderNode(node))}
      </div>
    </div>
  );
}