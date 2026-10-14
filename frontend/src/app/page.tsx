import "../../styles/globals.css";
import type { ReactElement } from "react";
import Head from "next/head";
import { TerminalWorkspace } from "../components/TerminalWorkspace";
import { AuthProvider } from "../contexts/AuthContext";
import { AuthGuard } from "../contexts/AuthGuard";

export default function Home(): ReactElement {
  return (
    <>
      <Head>
        <title>RANN Agent - AI Development Workspace</title>
        <meta name="description" content="Browser-based AI development workspace" />
      </Head>
      <AuthProvider>
        <AuthGuard>
          <TerminalWorkspace />
        </AuthGuard>
      </AuthProvider>
    </>
  );
}