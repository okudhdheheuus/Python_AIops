"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LogIn, UserPlus } from "lucide-react";

export default function LoginPage() {
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  // Login form
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);
  // Register form
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regError, setRegError] = useState<string | null>(null);
  const [regSuccess, setRegSuccess] = useState(false);
  const [regLoading, setRegLoading] = useState(false);

  const { login } = useAuth();
  const router = useRouter();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) return;
    setLoginLoading(true);
    setLoginError(null);
    const err = await login(username, password);
    if (err) {
      setLoginError(err);
    } else {
      router.push("/");
    }
    setLoginLoading(false);
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!regUsername || !regPassword) return;
    if (regPassword !== regConfirm) {
      setRegError("两次密码不一致");
      return;
    }
    setRegLoading(true);
    setRegError(null);
    setRegSuccess(false);
    try {
      const resp = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: regUsername,
          password: regPassword,
          email: regEmail || undefined,
          role: "admin",
        }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        setRegError((err as { detail?: string }).detail || "注册失败");
      } else {
        setRegSuccess(true);
        setRegUsername("");
        setRegPassword("");
        setRegConfirm("");
        setRegEmail("");
      }
    } catch {
      setRegError("无法连接后端服务");
    } finally {
      setRegLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900">
      <div className="w-full max-w-sm bg-gray-800/50 border border-gray-700 rounded-xl p-8">
        <div className="flex gap-0 mb-6 bg-gray-900 rounded-lg p-1">
          <button
            onClick={() => setActiveTab("login")}
            className={`flex-1 py-2 rounded-lg text-sm flex items-center justify-center gap-2 ${
              activeTab === "login" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
            }`}
          >
            <LogIn size={16} /> 登录
          </button>
          <button
            onClick={() => setActiveTab("register")}
            className={`flex-1 py-2 rounded-lg text-sm flex items-center justify-center gap-2 ${
              activeTab === "register" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
            }`}
          >
            <UserPlus size={16} /> 注册
          </button>
        </div>

        {activeTab === "login" ? (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">用户名</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="admin"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="••••••"
              />
            </div>

            {loginError && <div className="text-red-400 text-sm">{loginError}</div>}

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 py-2 rounded-lg text-white font-medium transition"
            >
              {loginLoading ? "登录中..." : "登录"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">用户名</label>
              <input
                value={regUsername}
                onChange={(e) => setRegUsername(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="输入用户名"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">邮箱 (可选)</label>
              <input
                type="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="admin@example.com"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">密码</label>
              <input
                type="password"
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="至少 6 位字符"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">确认密码</label>
              <input
                type="password"
                value={regConfirm}
                onChange={(e) => setRegConfirm(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="再次输入密码"
                required
              />
            </div>

            {regSuccess && <div className="text-green-400 text-sm">注册成功！请切换到登录标签页。</div>}
            {regError && <div className="text-red-400 text-sm">{regError}</div>}

            <button
              type="submit"
              disabled={regLoading}
              className="w-full bg-green-600 hover:bg-green-700 disabled:opacity-50 py-2 rounded-lg text-white font-medium transition"
            >
              {regLoading ? "注册中..." : "注册"}
            </button>
          </form>
        )}

        <p className="text-xs text-gray-500 mt-4 text-center">
          ITOps 智能运维自动化平台
        </p>
      </div>
    </div>
  );
}
