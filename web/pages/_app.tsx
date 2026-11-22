import type { AppProps } from "next/app";
import Head from "next/head";
import "@xyflow/react/dist/style.css";
import "../styles/globals.css";
import Layout from "../components/Layout";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>GraphGuard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </>
  );
}
