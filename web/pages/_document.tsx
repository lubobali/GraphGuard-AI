import { Head, Html, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta name="description" content="GraphGuard: an AML alert queue on synthetic data" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
