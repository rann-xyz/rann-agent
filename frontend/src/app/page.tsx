import "../../styles/globals.css";
import type { ReactElement } from "react";
import Head from "next/head";
import { TerminalWorkspace } from "../components/TerminalWorkspace";

export default function Home(): ReactElement {
  return (
    <>
      <Head>
        <title>RANN Agent - AI Development Workspace</title>
        <meta name="description" content="Browser-based AI development workspace" />
      </Head>
      <TerminalWorkspace />
    </>
  );
}