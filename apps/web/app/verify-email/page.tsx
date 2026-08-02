import { AuthShell } from "../../components/auth/auth-forms";

export default function VerifyEmailPage() {
  return <AuthShell title="Email verification" subtitle="Email verification is not configured for this environment."><p className="authNotice" role="status">Your account can continue without email verification until email delivery is configured.</p></AuthShell>;
}
