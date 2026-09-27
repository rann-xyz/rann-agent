/**
 * Editor Component - Monaco Editor integration
 */

import React, { useEffect, useRef } from 'react';
import EditorWorker from '@monaco-editor/plugins/lib/workers/editor/editor.worker?worker';
import { cn } from '../lib/utils';

interface EditorProps {
  filePath: string | null;
  className?: string;
}

let editorInstance: any = null;

export function Editor({ filePath, className }: EditorProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Monaco Editor initialization
    const initEditor = async () => {
      if (!containerRef.current) return;
      
      // Create worker
      const worker = new EditorWorker();
      worker.port.onmessage = () => {};

      // Monaco is loaded dynamically
      const monaco = await import('monaco-editor');

      editorInstance = monaco.editor.create(containerRef.current, {
        value: `// RANN Agent Project\n\nconsole.log("Hello, World!");\n\nfunction main() {\n  console.log("Starting agent...");\n}\n\nmain();`,
        language: 'python',
        theme: 'vs-dark',
        fontSize: 14,
        fontFamily: 'Consolas, Menlo, Monaco, monospace',
        renderLineHighlight: 'all',
        cursorBlinking: 'phase',
        cursorStyle: 'block',
        lineNumbers: 'on',
        minimap: { enabled: false },
        wordWrap: 'on',
        automaticLayout: true,
        tabSize: 4,
        insertSpaces: true,
      });
    };

    initEditor();

    return () => {
      if (editorInstance) {
        editorInstance.dispose();
      }
    };
  }, []);

  // Handle file save
  const handleSave = () => {
    if (editorInstance) {
      const value = editorInstance.getValue();
      console.log('Save file:', filePath, value);
    }
  };

  return (
    <div className={cn("h-full flex flex-col", className)}>
      {/* Editor Toolbar */}
      <div className="flex items-center justify-between px-3 py-1 bg-gray-900/50 border-b border-gray-800">
        <div className="text-xs text-gray-400">
          {filePath || 'Untitled'}
        </div>
        <div className="flex space-x-1">
          <button
            onClick={handleSave}
            className="px-2 py-1 text-xs text-gray-300 hover:text-gray-100 rounded hover:bg-gray-800"
            title="Save (Ctrl+S)"
          >
            💾 Save
          </button>
        </div>
      </div>

      {/* Editor Container */}
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}