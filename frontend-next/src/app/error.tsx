"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex items-center justify-center h-full p-8">
      <div className="max-w-md w-full bg-gray-800/50 border border-gray-700 rounded-xl p-6 text-center">
        <h2 className="text-lg font-semibold text-white mb-2">页面渲染出错</h2>
        <p className="text-sm text-gray-400 mb-4 break-all">{error.message}</p>
        <button
          onClick={reset}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white text-sm transition"
        >
          重试
        </button>
      </div>
    </div>
  );
}
