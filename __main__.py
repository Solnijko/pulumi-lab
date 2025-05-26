import pulumi
import pulumi_kubernetes as k8s

import storage.minio as minio
import storage.memcached as memcached
import monitoring.prometheus as prometheus
import monitoring.thanos as thanos

def namespace(name):
    k8s.core.v1.Namespace(name,
        metadata={"name": name}
    )
    return name

monitoring_ns = namespace("monitoring")
storage_ns = namespace("storage")

minio_release = minio.setup_minio(storage_ns)
memcached_release = memcached.setup_memcached(storage_ns)

curr_stack = pulumi.StackReference(f"{pulumi.get_organization()}/{pulumi.get_project()}/{pulumi.get_stack()}")
minio_url = curr_stack.get_output("minio_service_url")
minio_secret_key = curr_stack.get_output("minio_secret_key")
memcached_url = curr_stack.get_output("memcached_service_url")

prometheus_release = pulumi.Output.all(
    monitoring_ns, minio_url, minio_secret_key
).apply(lambda args: prometheus.setup_prometheus(args[0], args[1], args[2], minio_release))

thanos_store = curr_stack.get_output("thanos_store_url")

thanos_release = pulumi.Output.all(
    monitoring_ns, minio_url, minio_secret_key, thanos_store, memcached_url).apply(
    lambda args: thanos.setup_thanos(
    ns=args[0],
    minio_url=args[1],
    minio_secret_key=args[2],
    store=args[3],
    dependencies=[minio_release, memcached_release],
    cache_server=args[4]
    )
)