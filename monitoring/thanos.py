import pulumi
import pulumi_kubernetes.helm.v3 as k8s_helm

def setup_thanos(ns = "default", minio_url = "http://minio:9000", minio_secret_key = "minio", store = "some-store", cache_server = "http://memcached:11211", dependencies = []):
    query_runners = 2

    memcached_config = f"""
{{
  "type": "MEMCACHED",
  "config": {{
    "addresses": ["{cache_server}"],
    "timeout": "500ms",
    "max_idle_connections": 100,
    "max_async_concurrency": 10
  }}
}}
    """.strip().replace('\n', ' ')

    thanos = k8s_helm.Release(
        "thanos",
        name="thanos",
        opts=pulumi.ResourceOptions(
            ignore_changes=["checksum"],
            delete_before_replace=True,
            depends_on=dependencies
        ),
        chart="oci://registry-1.docker.io/bitnamicharts/thanos",
        version="16.0.4",
        namespace=ns,
        timeout=0,
        values={
            'objstoreConfig': f"""
type: s3
config:
    bucket: "thanos"
    endpoint: "{minio_url}"
    access_key: "minio"
    secret_key: "{minio_secret_key}"
    insecure: true
            """,
            'query': {
                'replicaCount': query_runners,
                'stores': [store],
                'extraFlags': [
                    "--query.promql-engine=thanos",
                    "--query.instant.default.max_source_resolution=1h",
                    "--query.auto-downsampling",
                ],
            },
            'queryFrontend': {
                'enabled': True,
                'replicaCount': 2,
                'extraFlags': [
                    f'--query-range.response-cache-config={memcached_config}',
                    f'--labels.response-cache-config={memcached_config}',
                    '--query-range.split-interval=6h',
                    f'--query-range.max-query-parallelism={query_runners}',
                ],
            },
        }
    )
    return thanos