import { AuthShell, VerifyEmailForm } from "../../components/auth/auth-forms";

export default function VerifyEmailPage() {
  return <AuthShell title="Email verification" subtitle="Confirming your email address."><VerifyEmailForm /></AuthShell>;
}
