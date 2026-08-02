import { AuthShell, ForgotPasswordForm } from "../../components/auth/auth-forms";

export default function ForgotPasswordPage() {
  return <AuthShell title="Reset your password" subtitle="Request a reset link for your Yoranix account."><ForgotPasswordForm /></AuthShell>;
}
