import { AuthShell, ResetPasswordForm } from "../../components/auth/auth-forms";

export default function ResetPasswordPage() {
  return <AuthShell title="Choose a new password" subtitle="Use a strong password to protect your workspace."><ResetPasswordForm /></AuthShell>;
}
