import SignupForm from "@/components/Auth/SignupForm";

export const metadata = {
  title: "Create Account - Thandev Security Platform",
  description: "Create your free Thandev account to access unlimited security scans, vulnerability assessments, and professional cybersecurity tools.",
  keywords: [
    "create account",
    "sign up",
    "free account",
    "security platform",
    "cybersecurity tools",
    "vulnerability scanner",
    "thandev account"
  ],
  openGraph: {
    title: "Create Account - Thandev Security Platform",
    description: "Create your free Thandev account to access unlimited security scans and vulnerability assessments.",
    type: "website",
    url: "https://thandev.com/auth/signup",
  },
  twitter: {
    card: "summary_large_image",
    title: "Create Account - Thandev Security Platform",
    description: "Create your free Thandev account to access unlimited security scans and vulnerability assessments.",
  },
  alternates: {
    canonical: "/auth/signup",
  },
};

export default function SignupPage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
            <span className="text-2xl font-bold tracking-tight">Thandev</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--fg)] mb-2">Create Your Account</h1>
          <p className="text-[var(--muted)]">Get unlimited access to our security scanning tools</p>
        </div>

        <SignupForm />

        <div className="mt-6 text-center">
          <p className="text-sm text-[var(--muted)]">
            Already have an account?{" "}
            <a href="/auth/signin" className="text-blue-600 hover:text-blue-700 font-medium">
              Sign in
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}

