<!-- markdownlint-disable -->
![Infrahub Logo](https://assets-global.website-files.com/657aff4a26dd8afbab24944b/657b0e0678f7fd35ce130776_Logo%20INFRAHUB.svg)
<!-- markdownlint-restore -->

# Infrahub by OpsMill

[Infrahub](https://github.com/opsmill/infrahub) by [OpsMill](https://opsmill.com) acts as a central hub to manage the data, templates and playbooks that powers your infrastructure. At its heart, Infrahub is built on 3 fundamental pillars:

- **A Flexible Schema**: A model of the infrastructure and the relation between the objects in the model, that's easily extensible.
- **Version Control**: Natively integrated into the graph database which opens up some new capabilities like branching, diffing, and merging data directly in the database.
- **Unified Storage**: By combining a graph database and git, Infrahub stores data and code needed to manage the infrastructure.

## Infrahub - Demo repository for Load Balancer & VIP

This repository is demoing the key Infrahub features for an example with servers, Load Balancer and VIP. Infrahub generates configurations that ansible deploys.

You can run this demo on your pc using docker, or using Github Codespaces.

## Running the demo on your pc

### Set environment variables

```shell
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"
```

### Install the Infrahub SDK

```shell
poetry install --no-interaction --no-ansi --no-root
```

### Start Infrahub

```shell
poetry run invoke start
```

### Load schema and data into Infrahub

This will create :

- Basics data (Account, Organization, ASN, and Tags)
- Locations data (Locations, and Prefixes)
- Servers data (VIP, Frontend and Load Balancers)
- Resource Managers (Prefix, IP and Number pools)

```shell
poetry run invoke load-schema load-data
```

## Running the demo in Github Codespaces

[Spin up in Github codespace](https://codespaces.new/opsmill/infrahub-demo-dc-fabric-develop)

## Demo flow

### 1. Add the repository into Infrahub (Replace GITHUB_USER and GITHUB_TOKEN)

> [!NOTE]
> Reference the [Infrahub documentation](https://docs.infrahub.app/guides/repository) for the multiple ways this can be done.

```graphql
mutation AddCredential {
  CorePasswordCredentialCreate(
    data: {
      name: {value: "my-git-credential"},
      username: {value: "<GITHUB_USERNAME>"},
      password: {value: "<GITHUB_TOKEN>"}
    }
  ) {
    ok
    object {
      hfid
    }
  }
}


mutation AddRepository{
  CoreRepositoryCreate(
    data: {
      name: { value: "infrahub-demo-vip-and-lb" }
      location: { value: "https://github.com/GITHUB_USER/infrahub-demo-vip-and-lb.git" }
      # The HFID return from the previous mutation. Will be the name of the credentials
      credential: { hfid: "my-git-credential" }
    }
  ) {
    ok
    object {
      id
    }
  }
}
```