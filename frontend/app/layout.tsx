import "./globals.css";
import React from "react";
import Sidebar from "../components/Sidebar";

export const metadata = {
  title: "SmartShelf — Retail AI Dashboard",
  description: "Production-grade Retail AI system — Demand, Price, Inventory",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-layout">
          <Sidebar />
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
