import ipaddress
import logging

from typing import Dict, List, Optional

from infrahub_sdk import InfrahubClient, InfrahubNode, NodeStore
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.exceptions import GraphQLError

# flake8: noqa
# pylint: skip-file

ORGANIZATIONS = (
    # name, type
    # -- Tenant
    ("Duff", "tenant"),
    # -- Manufacturer
    ("Juniper", "manufacturer"),
    ("Cisco", "manufacturer"),
    # -- Provider
    ("Interxion", "provider"),
    ("Equinix", "provider"),
    ("Colt Technology Services", "provider"),
    ("Lumen", "provider"),
    ("Arelion", "provider"),
)

ASNS = (
    # asn, description, organization
    (1299, "AS1299 - Arelion", "Arelion"),
    (64496, "AS64496 - Duff", "Duff"),
    (8220, "AS8220 - Colt Technology Services", "Colt Technology Services"),
    (3356, "AS3356 - Lumen", "Lumen"),
)

VRFS = (
    # Name, Description, is_global, RD
    # -- Global VRF
    ("Internet", "Internet VRF", "33930:100"),
    ("Production", "Production VRF", "33930:1"),
    ("Development", "Development VRF", "33930:2"),
    ("DMZ", "DMZ VRF", "33930:666"),
)

PLATFORMS = (
    # name, nornir_platform, napalm_driver, netmiko_device_type, ansible_network_os
    ("Juniper JunOS", "junos", "junos", "juniper_junos", "junos"),
    ("Cisco IOS-XE", "iosxe", "ios", "cisco_xe", "ios"),
    ("Debian", "linux", None, "linux", "community.general.linux"),
    ("VMware ESXi", "esxi", None, "vmware_esxi", "vmware_esxi"),
    ("Windows Server 2018", "windows", None, None, "windows"),
)

GROUPS = (
    # name, description
    ("load_balancers", "Haproxy Load Balancers"),
    ("web_servers", "Web Servers"),
)

COUNTRIES = (
    # name, shortname
    # Europe
    ("France", "FR"),
    ("Germany", "DE"),
    ("Netherlands", "NL"),
    ("United States of America", "USA"),
    ("Canada", "CA"),
)

METRO_AREAS = (
    # name, shortname, parent (COUNTRY)
    # -- France
    # France
    ("Paris", "PAR", "France"),
    ("Frankfurt", "FRA", "Germany"),
    ("Amsterdam", "AMS", "Netherlands"),
)

SITES = (
    # name, shortname, facility_id, physical_address, gps_coordinates, Pop Role, Status, parent (METRO AREA), provider
    # -- France
    # Paris
    ("EQX2.FRA.DE", "EQX-FRA2", "FRA2", "", "", "dc", "active", "Frankfurt", "Equinix"),
    ("ITX9.AMS.NL", "EQX-FRA2", "FRA2", "", "", "dc", "active", "Amsterdam", "Interxion"),
    ("ITX7.PAR.FR", "PAR7", "PAR7", "", "", "dc", "active", "Paris", "Interxion"),
)

# We could already use the Pool from the supernet instead of indicating the smaller prefixes.
PREFIXES = [
    # CGNAT
    {"prefix": "100.100.0.0/16", "location": None, "role": "supernet", "vrf": "Internet"},
    {"prefix": "100.100.1.0/24", "location": "EQX2.FRA.DE", "role": "technical", "vrf": "Internet"},
    {"prefix": "100.100.2.0/24", "location": "ITX7.PAR.FR", "role": "technical", "vrf": "Internet"},
    {"prefix": "100.100.3.0/24", "location": "ITX9.AMS.NL", "role": "technical", "vrf": "Internet"},
    # Public
    {"prefix": "203.0.112.0/22", "location": None, "role": "supernet", "vrf": "Internet"},
    {"prefix": "203.0.112.0/24", "location": "EQX2.FRA.DE", "role": "public", "vrf": "Internet"},
    {"prefix": "203.0.113.0/24", "location": "ITX7.PAR.FR", "role": "public", "vrf": "Internet"},
    {"prefix": "203.0.113.0/24", "location": "ITX9.AMS.NL", "role": "public", "vrf": "Internet"},
    # Private
    {"prefix": "10.100.0.0/14", "location": None, "role": "supernet", "vrf": None},
    {"prefix": "10.101.0.0/16", "location": "EQX2.FRA.DE", "role": "supernet", "vrf": None},
    {"prefix": "10.101.0.0/24", "location": "EQX2.FRA.DE", "role": "dmz", "vrf": "DMZ"},
    {"prefix": "10.101.1.0/24", "location": "EQX2.FRA.DE", "role": "server", "vrf": "Production"},
    {"prefix": "10.101.2.0/24", "location": "EQX2.FRA.DE", "role": "server", "vrf": "Development"},
    {"prefix": "10.102.0.0/16", "location": "ITX7.PAR.FR", "role": "supernet", "vrf": None},
    {"prefix": "10.102.0.0/24", "location": "ITX7.PAR.FR", "role": "dmz", "vrf": "DMZ"},
    {"prefix": "10.102.1.0/24", "location": "ITX7.PAR.FR", "role": "server", "vrf": "Production"},
    {"prefix": "10.102.2.0/24", "location": "ITX7.PAR.FR", "role": "server", "vrf": "Development"},
    {"prefix": "10.103.0.0/16", "location": "ITX9.AMS.NL", "role": "supernet", "vrf": None},
    {"prefix": "10.103.0.0/24", "location": "ITX9.AMS.NL", "role": "dmz", "vrf": "DMZ"},
    {"prefix": "10.103.1.0/24", "location": "ITX9.AMS.NL", "role": "server", "vrf": "Production"},
    {"prefix": "10.103.2.0/24", "location": "ITX9.AMS.NL", "role": "server", "vrf": "Development"},
]


INTERNAL_DOMAIN = "duff.ninja"
EXTERNAL_DOMAIN = "duff.io"

# --- Utils
# Helper function to generate pool name
def generate_pool_name(vrf_label: str, site_name: str, prefix: str, role: str) -> str:
    prefix_common = extract_common_prefix(prefix)
    if vrf_label:
        return f"{role}.{vrf_label.lower()}.{site_name.lower()}-{prefix_common}"
    else:
        return f"{role}.{site_name.lower()}-{prefix_common}"

def extract_common_prefix(prefix: str) -> str:
    # Create an IP network object
    net = ipaddress.ip_network(prefix, strict=False)

    # Get the network address in binary form
    network_address = net.network_address
    # Convert the network address to a string
    net_str = str(network_address)

    # Calculate how many full octets (for IPv4) to extract
    if isinstance(network_address, ipaddress.IPv4Address):
        # Full octets (each 8 bits)
        full_octets = net.prefixlen // 8

        # Handle partial octet
        partial_bits = net.prefixlen % 8
        if partial_bits > 0:
            # Extract the first full octets
            octets = net_str.split('.')[:full_octets]
            # Add the partial octet if necessary
            partial_octet = int(net_str.split('.')[full_octets]) & (0xFF << (8 - partial_bits))
            octets.append(str(partial_octet))
            return '.'.join(octets) + f"/{net.prefixlen}"
        else:
            return '.'.join(net_str.split('.')[:full_octets]) + f"/{net.prefixlen}"

    elif isinstance(network_address, ipaddress.IPv6Address):
        # Full hextets (each 16 bits)
        full_hextets = net.prefixlen // 16
        partial_bits = net.prefixlen % 16
        if partial_bits > 0:
            hextets = net_str.split(':')[:full_hextets]
            partial_hextet = int(net_str.split(':')[full_hextets], 16) & (0xFFFF << (16 - partial_bits))
            hextets.append(f'{partial_hextet:x}')
            return ':'.join(hextets) + f"/{net.prefixlen}"
        else:
            return ':'.join(net_str.split(':')[:full_hextets]) + f"/{net.prefixlen}"


async def execute_batch(batch: InfrahubBatch, log: logging.Logger) -> None:
    try:
        async for node, _ in batch.execute():
            object_reference = None
            if node.hfid:
                object_reference = node.hfid[0]
            elif node._schema.default_filter:
                accessor = node._schema.default_filter.split("__")[0]
                object_reference = getattr(node, accessor).value
            if object_reference:
                log.debug(f"- Created [{node._schema.kind}] '{object_reference}'")
            else:
                log.debug(f"- Created [{node._schema.kind}]")
    except GraphQLError as exc:
        log.debug(f"- Creation failed due to {exc}")


async def create_and_save(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    object_name: str,
    kind_name: str,
    data: Dict,
    allow_upsert: Optional[bool] = True,
    retrieved_on_failure: Optional[bool] = False,
) -> InfrahubNode:
    """Creates an object, saves it and handles failures."""
    try:
        obj = await client.create(branch=branch, kind=kind_name, data=data)
        await obj.save(allow_upsert=allow_upsert)
        log.debug(f"- Created {obj._schema.kind} - {object_name}")
        client.store.set(key=object_name, node=obj)
    except GraphQLError as exc:
        log.debug(f"- Creation failed for {obj._schema.kind} - {object_name} due to {exc}")
        if retrieved_on_failure:
            obj = await client.get(kind=kind_name, name__value=object_name)
            client.store.set(key=object_name, node=obj)
            log.debug(f"- Retrieved {obj._schema.kind} - {object_name}")
    return obj


async def create_and_add_to_batch(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    object_name: str,
    kind_name: str,
    data: Dict,
    batch: InfrahubBatch,
    allow_upsert: Optional[bool] = True,
) -> InfrahubNode:
    """Creates an object and adds it to a batch for deferred saving."""
    obj = await client.create(branch=branch, kind=kind_name, data=data)
    batch.add(task=obj.save, allow_upsert=allow_upsert, node=obj)
    log.debug(f"- Added to batch [{obj._schema.kind}] '{object_name}'")
    client.store.set(key=object_name, node=obj)
    return obj


# --- RUN
async def run(client: InfrahubClient, log: logging.Logger, branch: str, **kwargs) -> None:
    log.info("Creating Organizations and ASNs")
    batch = await client.create_batch()
    # ---- Organization
    for org in ORGANIZATIONS:
        org_data = {
            "name": {"value": org[0], "is_protected": True},
        }
        org_obj = await client.create(
            branch=branch,
            kind=f"Organization{org[1].title()}",
            data=org_data,
        )
        batch.add(task=org_obj.save, allow_upsert=True, node=org_obj)
        client.store.set(key=org[0], node=org_obj)

    async for node, _ in batch.execute():
        accessor = node._schema.human_friendly_id[0].split("__")[0]
        log.debug(f"- Created {node._schema.kind} - {getattr(node, accessor).value}")

    duff_org_obj = client.store.get(kind="OrganizationTenant", key="Duff")

    # ---- Autonomous System
    organizations_dict = {name: type for name, type in ORGANIZATIONS}
    batch = await client.create_batch()
    for asn in ASNS:
        organization_type = organizations_dict.get(asn[2], None)
        asn_name = f"AS{asn[0]}"
        data_asn = {
            "name": {"value": asn_name},
            "asn": {"value": asn[0]},
            "description": {"value": asn[1]},
        }
        if organization_type:
            data_asn["organization"] = {"id": client.store.get(kind=f"Organization{organization_type.title()}", key=asn[2]).id}

        asn_obj = await client.create(
            branch=branch,
            kind="InfraAutonomousSystem",
            data=data_asn,
        )
        batch.add(task=asn_obj.save, allow_upsert=True, node=asn_obj)
        client.store.set(key=asn[0], node=asn_obj)

    await execute_batch(batch=batch, log=log)

    log.info("Creating Device Types and Platforms")
    # ---- Platforms
    batch = await client.create_batch()
    for platform in PLATFORMS:
        manufacturer_name = platform[0].split()[0].title()
        manufacturer = client.store.get(key=manufacturer_name, kind="OrganizationManufacturer", raise_when_missing=False)
        platform_data = {
            "name": platform[0],
            "nornir_platform": platform[1],
            "napalm_driver": platform[2],
            "netmiko_device_type": platform[3],
            "ansible_network_os": platform[4],
        }
        if manufacturer:
            platform_data["manufacturer"] = {"id": manufacturer.id}

        platform_obj = await client.create(
            branch=branch,
            kind="InfraPlatform",
            data=platform_data,
        )
        batch.add(task=platform_obj.save, allow_upsert=True, node=platform_obj)
        client.store.set(key=platform[0], node=platform_obj)

    await execute_batch(batch=batch, log=log)

    log.info("Creating standard groups")
    batch = await client.create_batch()
    for group in GROUPS:
        group_data = {
            "name": group[0],
            "label": group[1],
        }
        group_obj = await client.create(
            branch=branch,
            kind="CoreStandardGroup",
            data=group_data,
        )
        batch.add(task=group_obj.save, allow_upsert=True, node=group_obj)
        client.store.set(key=group[0], node=group_obj)

    await execute_batch(batch=batch, log=log)

    log.info("Creating Locations")
    # ---- Countries
    batch = await client.create_batch()
    for country in COUNTRIES:
        country_data = {
            "name": country[0],
            "shortname": country[1],
        }

        country_obj = await client.create(
            branch=branch,
            kind="LocationCountry",
            data=country_data,
        )
        batch.add(task=country_obj.save, allow_upsert=True, node=country_obj)
        client.store.set(key=country[0], node=country_obj)

    await execute_batch(batch=batch, log=log)

    # ---- Metro Areas
    batch = await client.create_batch()
    for metro_area in METRO_AREAS:
        metro_area_parent_obj = client.store.get(kind="LocationCountry", key=metro_area[2])
        metro_area_parent_id = metro_area_parent_obj.id
        metro_area_full_name = f"{ metro_area[1]}.{metro_area_parent_obj.shortname.value}"
        metro_area_data = {
            "name": metro_area[0],
            "shortname": metro_area[1],
            "description": metro_area_full_name,
            "parent": {"id": metro_area_parent_id},
        }

        metro_area_obj = await client.create(
            branch=branch,
            kind="LocationMetro",
            data=metro_area_data,
        )
        batch.add(task=metro_area_obj.save, allow_upsert=True, node=metro_area_obj)

    async for node, _ in batch.execute():
        accessor = node._schema.default_filter.split("__")[0]
        client.store.set(key=node.name.value, node=node)
        log.debug(f"- Created [{node._schema.kind}] '{getattr(node, accessor).value}'")

    # ---- Sites
    batch = await client.create_batch()
    for site in SITES:
        site_parent_id = client.store.get(kind="LocationMetro", key=site[7]).id
        site_data = {
            "name": site[0],
            "shortname": site[1],
            "parent": {"id": site_parent_id},
            "site_type": site[5],
            "status": site[6],
            "owner": {"id": duff_org_obj.id},
        }
        if site[2]:
            site_data["facility_id"] = site[2]
            if site[8]:
                site_data["provider"] = client.store.get(kind="OrganizationProvider", key=site[8]).id
        if site[3]:
            site_data["physical_address"] = site[3]
        if site[4]:
            site_data["gps_coordinates"] = site[4]

        site_obj = await client.create(
            branch=branch,
            kind="LocationSite",
            data=site_data,
        )
        batch.add(task=site_obj.save, allow_upsert=True, node=site_obj)
        client.store.set(key=site[0], node=site_obj)

    await execute_batch(batch=batch, log=log)

    log.info("Creating VRFs")
    batch = await client.create_batch()
    for vrf in VRFS:
        vrf_name = vrf[0]
        vrf_description = vrf[1]
        vrf_rd = vrf[2]

        vrf_data = {}
        if vrf_rd != "":
            vrf_data["vrf_rd"] = {"value": vrf_rd}

        vrf_data["name"] = {"value": vrf_name}
        vrf_data["description"] = {"value": vrf_description}

        vrf_obj = await client.create(
            branch=branch,
            kind="InfraVRF",
            data=vrf_data,
        )
        batch.add(task=vrf_obj.save, allow_upsert=True, node=vrf_obj)
        client.store.set(key=vrf_name, node=vrf_obj)

    await execute_batch(batch=batch, log=log)

    # ---- Prefixes
    default_ip_namespace_obj = await client.get(kind="IpamNamespace", name__value="default")
    log.info("Creating Prefixes")
    batch = await client.create_batch()
    for prefix in PREFIXES:
        pfx = prefix["prefix"]
        pfx_location = prefix["location"]
        pfx_role = prefix["role"]
        pfx_status = "active"
        pfx_vrf = prefix["vrf"]
        pfx_descr = f"{pfx_role}"
        if pfx_vrf:
            pfx_descr += f".{pfx_vrf.lower()}"
        elif pfx_location:
            pfx_descr += f".{pfx_location.lower()}"

        pfx_data = {
            "prefix": pfx,
            "description": {"value": pfx_descr},
            "role": {"value": pfx_role},
            "status": {"value": pfx_status},
        }
        if pfx_location:
            location_obj = client.store.get(kind="LocationSite", key=f"{pfx_location}", raise_when_missing=False)
            if location_obj:
                pfx_data["location"] = location_obj.id

        if pfx_role == "supernet":
            pfx_data["member_type"] = "prefix"

        if pfx_vrf:
            pfx_data["vrf"] = client.store.get(kind="InfraVRF", key=f"{pfx_vrf}", raise_when_missing=False).id

        await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=pfx,
            kind_name="IpamIPPrefix",
            data=pfx_data,
            batch=batch,
        )

    await execute_batch(batch=batch, log=log)

    for prefix in PREFIXES:
        pfx = prefix["prefix"]
        pfx_role = prefix["role"]
        if pfx_role in ("technical", "dmz", "server"):
            gw_addr = f"{str(ipaddress.ip_network(pfx, strict=False)[-2])}/{pfx.split('/')[1]}"
            gw_data = {
                "address": gw_addr
            }
            gw_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=gw_addr,
                kind_name="IpamIPAddress",
                data=gw_data,
            )
            pfx_obj = client.store.get(kind="IpamIPPrefix", key=pfx, raise_when_missing=False)
            if pfx_obj:
                pfx_obj.gateway= gw_obj
                await pfx_obj.save()

    # ---- Resource Pools
    log.info("Creating Resource Pools")
    asn_pool_data = {
        "name": "loadbalancer-private-asn",
        "description": "Pool for LB Private ASNs",
        "node": "InfraAutonomousSystem",
        "node_attribute":"asn",
        "start_range": 65101,
        "end_range": 65299,
    }
    await create_and_save(
        client=client,
        log=log,
        branch=branch,
        object_name="loadbalancer-private-asn",
        kind_name="CoreNumberPool",
        data=asn_pool_data,
        allow_upsert=False
    )

    batch = await client.create_batch()
    for prefix in PREFIXES:
        pfx = prefix["prefix"]
        pfx_location = prefix["location"]
        pfx_role = prefix["role"]
        pfx_vrf = prefix["vrf"]
        pfx_descr = f"{pfx_role}"
        if pfx_vrf and pfx_vrf != "DMZ":
            pfx_descr += f".{pfx_vrf.lower()}"
        if pfx_location:
            pfx_descr += f".{pfx_location.lower()}"

        pool_name = f"{pfx_descr}-{extract_common_prefix(prefix=pfx)}"
        pool_desc = f"Pool for {pfx_descr}"
        pool_data = {
            "name": pool_name ,
            "description": pool_desc,
            "ip_namespace": {"id": default_ip_namespace_obj.id},
            "default_prefix_length": 24,
        }
        kind = None
        prefix_obj = client.store.get(kind="IpamIPPrefix", key=pfx, raise_when_missing=False)
        if prefix_obj:
            pool_data["resources"] = [prefix_obj]

        if prefix["role"] == "supernet":
            pool_data["default_prefix_type"] = {"value": "IpamIPPrefix" }
            pool_data["default_member_type"] = {"value": "address" }
            kind = "CoreIPPrefixPool"
        else:
            pool_data["default_address_type"] = {"value": "IpamIPAddress" }
            kind = "CoreIPAddressPool"

        if prefix["role"] == "public":
            pool_data["default_prefix_length"] = 32

        await create_and_add_to_batch(
            client=client,
            log=log,
            branch=branch,
            object_name=pool_name,
            kind_name=kind,
            data=pool_data,
            batch=batch,
        )
    await execute_batch(batch=batch, log=log)


    # ---- Frontend Servers and VIPs
    web_srv_grp = client.store.get(kind="CoreStandardGroup", key="web_servers")
    lb_grp = client.store.get(kind="CoreStandardGroup", key="load_balancers")
    all_frontends = []
    all_load_balancers = []
    for site in SITES:
        site_name = site[0]

        # Create 4 Frontend Servers per site
        for i in range(1, 5):
            # Set VRF for server (Production VRF for the first 3, Development VRF for the 4th)
            if i < 4:
                site_vrf = client.store.get(kind="InfraVRF", key="Production", raise_when_missing=False)
                vrf_label = "Production"
            else:
                site_vrf = client.store.get(kind="InfraVRF", key="Development", raise_when_missing=False)
                vrf_label = "Development"

            # Create frontend server data
            hostname = f"frontend{i}.{vrf_label.lower()}.{site_name.lower()}.{INTERNAL_DOMAIN}"
            frontend_server_data = {
                "hostname": hostname,
                "environment": "production" if vrf_label == "Production" else "development",
                "status": "active",
                "organization": {"id": duff_org_obj.id},
                "vrf": {"id": site_vrf.id},
            }

            # Create frontend server object
            frontend_server_obj = await create_and_save(
                client=client,
                log=log,
                branch=branch,
                object_name=hostname,
                kind_name="ServerFrontend",
                data=frontend_server_data,
            )
            all_frontends.append(frontend_server_obj.id)
            # Get prefix for the site from the PREFIXES data
            frontend_prefix = next((pfx["prefix"] for pfx in PREFIXES if pfx["location"] == site_name and pfx["role"] == "server" and pfx["vrf"] == vrf_label), None)

            if frontend_prefix:
                # Generate the frontend IP pool name using the new naming convention
                frontend_ip_pool_name = generate_pool_name(vrf_label, site_name, frontend_prefix, "server")
                frontend_ip_pool = client.store.get(kind="CoreIPAddressPool", key=frontend_ip_pool_name, raise_when_missing=False)

                # Allocate IP for the frontend server from the correct pool
                if frontend_ip_pool:
                    frontend_ip_obj = await client.allocate_next_ip_address(
                        resource_pool=frontend_ip_pool,
                        identifier=hostname,
                        data={"server": frontend_server_obj.id}
                    )

        # Create 3 VIPs per site (2 for production, 1 for development)
        for j in range(1, 4):
            # Set VRF for VIP (Production VRF for the first 2, Development VRF for the 3rd)
            if j < 3:
                vip_vrf = client.store.get(kind="InfraVRF", key="Production", raise_when_missing=False)
                vip_label = "Production"
                frontend_servers_for_vip_range = range(1, 4)
            else:
                vip_vrf = client.store.get(kind="InfraVRF", key="Development", raise_when_missing=False)
                vip_label = "Development"
                frontend_servers_for_vip_range = range(4, 5)

            # Create VIP hostname and data
            vip_hostname = f"vip{j}.{vip_label.lower()}.{site_name.lower()}.{EXTERNAL_DOMAIN}"
            vip_data = {
                "hostname": vip_hostname,
                "mode": "http",  # Assuming HTTP for the VIP
                "balance": "roundrobin",  # Assuming roundrobin for load balancing
                "status": "active",
                "vrf": {"id": vip_vrf.id},
            }

            # Get prefix for the site from the PREFIXES data (public internet)
            vip_prefix = next((pfx["prefix"] for pfx in PREFIXES if pfx["location"] == site_name and pfx["role"] == "public" and pfx["vrf"] == "Internet"), None)

            if vip_prefix:
                # Generate the VIP IP pool name using the new naming convention
                vip_ip_pool_name = generate_pool_name("internet", site_name, vip_prefix, "public")
                vip_ip_pool = client.store.get(kind="CoreIPAddressPool", key=vip_ip_pool_name, raise_when_missing=False)

                # Allocate VIP IP address from the correct pool
                if vip_ip_pool:
                    vip_ip_obj = await client.allocate_next_ip_address(
                        resource_pool=vip_ip_pool,
                        identifier=vip_hostname,
                    )
                    vip_data["ip_address"] = {"id": vip_ip_obj.id}

            # Create VIP object
            vip_obj = await create_and_save(
                    client=client,
                    log=log,
                    branch=branch,
                    object_name=vip_hostname,
                    kind_name="InfraVIP",
                    data=vip_data,
                )

            # Associate the frontend servers created above with the VIP
            frontend_servers_for_vip = [
                client.store.get(kind="ServerFrontend", key=f"frontend{k}.{vip_label.lower()}.{site_name.lower()}.{INTERNAL_DOMAIN}") for k in frontend_servers_for_vip_range
            ]
            # vip_obj.frontend_servers.fetch()
            frontend_servers = [server.id for server in frontend_servers_for_vip]
            await vip_obj.add_relationships(relation_to_update="frontend_servers", related_nodes=frontend_servers)
            await vip_obj.save()

        lb_vrf = client.store.get(kind="InfraVRF", key="Production", raise_when_missing=False)
        vrf_label = "Production"

        # Create Load Balancer hostname
        lb_hostname = f"lb.dmz.{site_name.lower()}.{INTERNAL_DOMAIN}"

        # Create Load Balancer data
        load_balancer_data = {
            "hostname": lb_hostname,
            "environment": "production",
            "status": "active",
            "organization": {"id": duff_org_obj.id},
            "vrf": {"id": lb_vrf.id},
        }

        # Create the Load Balancer object
        load_balancer_obj = await create_and_save(
            client=client,
            log=log,
            branch=branch,
            object_name=lb_hostname,
            kind_name="ServerLoadBalancer",
            data=load_balancer_data,
        )

        all_load_balancers.append(load_balancer_obj.id)

        # --- Allocate Private IP Address ---
        # Get private prefix for the site from the PREFIXES data
        private_prefix = next((pfx["prefix"] for pfx in PREFIXES if pfx["location"] == site_name and pfx["role"] == "dmz" and pfx["vrf"] == "DMZ"), None)

        if private_prefix:
            # Generate the Load Balancer private IP pool name using the new naming convention
            private_ip_pool_name = generate_pool_name(None, site_name, private_prefix, "dmz")
            private_ip_pool = client.store.get(kind="CoreIPAddressPool", key=private_ip_pool_name, raise_when_missing=False)

            # Allocate private IP for the Load Balancer from the correct pool
            if private_ip_pool:
                private_ip_obj = await client.allocate_next_ip_address(
                    resource_pool=private_ip_pool,
                    identifier=lb_hostname,
                    data={"description": load_balancer_obj.hostname.value}
                )

                # Assign the allocated private IP to the Load Balancer
                if private_ip_obj:
                    load_balancer_obj.ip_address = {"id": private_ip_obj.id}

        # --- Allocate Public IP Address ---
        # Get public prefix for the site from the PREFIXES data
        tech_prefix = next((pfx["prefix"] for pfx in PREFIXES if pfx["location"] == site_name and pfx["role"] == "technical" and pfx["vrf"] == "Internet"), None)

        if tech_prefix:
            # Generate the Load Balancer public IP pool name using the new naming convention
            tech_ip_pool_name = generate_pool_name("internet", site_name, tech_prefix, "technical")
            tech_ip_pool = client.store.get(kind="CoreIPAddressPool", key=tech_ip_pool_name, raise_when_missing=False)

            # Allocate public IP for the Load Balancer from the correct pool
            if tech_ip_pool:
                tech_ip_obj = await client.allocate_next_ip_address(
                    resource_pool=tech_ip_pool,
                    identifier=lb_hostname,
                    data={"description": load_balancer_obj.hostname.value}
                )
                # Assign the allocated public IP to the Load Balancer
                if tech_ip_obj:
                    load_balancer_obj.public_ip_address = {"id": tech_ip_obj.id}

        # Save the Load Balancer object with the assigned private and public IPs
        await load_balancer_obj.save()

    await web_srv_grp.add_relationships(relation_to_update="members", related_nodes=all_frontends)
    await lb_grp.add_relationships(relation_to_update="members", related_nodes=all_load_balancers)
