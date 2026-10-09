import { RoleHome } from "@/components/app/role-home";

export default function AdminHome() {
  return <RoleHome roles={["station_admin", "super_admin"]} />;
}
