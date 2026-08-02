import { AuthShell, RegisterForm } from "../../components/auth/auth-forms";

export default function RegisterPage() {
  return <AuthShell title="Create your Yoranix account" subtitle="Provision your organisation, workspace, and owner access in one secure step."><RegisterForm /></AuthShell>;
}
