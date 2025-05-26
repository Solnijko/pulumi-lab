import pulumi
from pulumi_kubernetes.helm.v3 import Release

def setup_memcached(ns):
    memcached = Release(
        "memcached",
        chart="oci://registry-1.docker.io/bitnamicharts/memcached",
        version="7.8.3",
        namespace=ns,
        values={
            "replicaCount": 1,
            "securityContext": {
                "enabled": True
            }
        }
    )

    pulumi.export("memcached_service_url", f"memcached.{ns}.svc.cluster.local:11211")
    return memcached
