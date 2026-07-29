import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { AuthProvider } from "@/lib/auth";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ITOps Platform",
  description: "智能运维管理平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.className} bg-gray-900 text-white flex h-screen`}>
        <AuthProvider>
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
