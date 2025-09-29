import SigninForm from "@/components/Auth/SigninForm";

export const metadata = {
  title: "Sign In - Thandev Security Platform",
  description: "Sign in to your Thandev account to access unlimited security scans, vulnerability assessments, and professional cybersecurity tools.",
  keywords: [
    "sign in",
    "login",
    "thandev account",
    "security platform",
    "cybersecurity tools",
    "vulnerability scanner"
  ],
  openGraph: {
    title: "Sign In - Thandev Security Platform",
    description: "Sign in to your Thandev account to access unlimited security scans and vulnerability assessments.",
    type: "website",
    url: "https://thandev.com/auth/signin",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sign In - Thandev Security Platform",
    description: "Sign in to your Thandev account to access unlimited security scans and vulnerability assessments.",
  },
  alternates: {
    canonical: "/auth/signin",
  },
};

export default function SigninPage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
            <span className="text-2xl font-bold tracking-tight">Thandev</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--fg)] mb-2">Welcome Back</h1>
          <p className="text-[var(--muted)]">Sign in to continue scanning</p>
        </div>

        <SigninForm />

        <div className="mt-6 text-center">
          <p className="text-sm text-[var(--muted)]">
            Don't have an account?{" "}
            <a href="/auth/signup" className="text-blue-600 hover:text-blue-700 font-medium">
              Create one
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}

