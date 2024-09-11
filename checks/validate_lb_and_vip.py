from collections import defaultdict
from infrahub_sdk.checks import InfrahubCheck


class InfrahubCheckLBVIPBackendLocationEnvironment(InfrahubCheck):
    query = "lb_and_vip_env"

    def validate(self, data):
        location_issues = defaultdict(lambda: defaultdict(int))
        location_id_by_name = {}

        if data["ServerLoadBalancer"]["edges"]:
            load_balancers = data["ServerLoadBalancer"]["edges"]

            for lb_edge in load_balancers:
                lb_node = lb_edge["node"]

                lb_hostname = lb_node["hostname"]["value"]
                lb_environment = lb_node["environment"]["value"]
                tmp_loc = lb_node["ip_address"]["node"]["ip_prefix"]["node"]["location"]["node"]
                if tmp_loc:
                    lb_location = lb_node["ip_address"]["node"]["ip_prefix"]["node"]["location"]["node"]["name"]["value"]
                    lb_location_id = lb_node["ip_address"]["node"]["ip_prefix"]["node"]["location"]["node"]["id"]
                    location_id_by_name[lb_location] = lb_location_id

                # Check VIPs
                for vip_edge in lb_node["virtual_ips"]["edges"]:
                    vip_node = vip_edge["node"]
                    vip_hostname = vip_node["hostname"]["value"]
                    vip_location = vip_node["ip_address"]["node"]["ip_prefix"]["node"]["location"]["node"]["name"]["value"]

                    if vip_location != lb_location:
                        location_issues[lb_location]["total"] += 1
                        self.log_error(
                            message=f"VIP {vip_hostname} is in location {vip_location}, which does not match LB {lb_hostname} (Location: {lb_location})",
                            object_id=lb_node["id"],
                            object_type="load_balancer",
                        )
                        continue

                    # Check Frontend servers for each VIP
                    for frontend_edge in vip_node["frontend_servers"]["edges"]:
                        frontend_node = frontend_edge["node"]
                        frontend_hostname = frontend_node["hostname"]["value"]
                        frontend_environment = frontend_node["environment"]["value"]
                        frontend_location = frontend_node["ip_address"]["node"]["ip_prefix"]["node"]["location"]["node"]["name"]["value"]

                        if frontend_location != lb_location or frontend_environment != lb_environment:
                            location_issues[lb_location]["total"] += 1
                            self.log_error(
                                message=f"Frontend {frontend_hostname} for VIP {vip_hostname} is in location {frontend_location} or environment {frontend_environment}, which does not match LB {lb_hostname} (Location: {lb_location}, Environment: {lb_environment})",
                                object_id=lb_node["id"],
                                object_type="load_balancer",
                            )

            # Check if there are location issues
            for location_name, issues in location_issues.items():
                if issues["total"] > 0:
                    self.log_error(
                        message=f"{location_name} has {issues['total']} VIPs or Frontends that do not match the Load Balancer location or environment.",
                        object_id=location_id_by_name[location_name],
                        object_type="location",
                    )
                else:
                    return
