import pulumi
import pulumi_kubernetes as k8s
from   pulumi_random import RandomPassword

def setup_minio(ns):
    minio_pv = k8s.core.v1.PersistentVolume(
        "minio-pv",
        metadata={
            "name": "minio-pv",
            "namespace": ns,
        },
        spec={
            "access_modes": ["ReadWriteOnce"],
            "capacity": {
                "storage": "10Gi"
            },
            "host_path": {
                "path": "/data",
            },
        }
    )

    minio_pvc = k8s.core.v1.PersistentVolumeClaim(
        "minio-pvc",
        metadata={
            "name": "minio-pvc",
            "namespace": ns,
        },
        opts=pulumi.ResourceOptions(
            depends_on=[minio_pv],
        ),
        spec={
            "accessModes": ["ReadWriteOnce"],
            "resources": {
                "requests": {
                    "storage": "10Gi",
                },
            },
        },
    )

    minio_secret_key = RandomPassword("minio_password",
        special=False,
        length=16
    )

    minio = k8s.helm.v3.Release(
        "minio-release",
        chart="minio",
        repository_opts={
            "repo": "https://charts.bitnami.com/bitnami",
        },
        version="14.6.10",
        name="minio",
        namespace=ns,
        timeout=0,
        opts=pulumi.ResourceOptions(
            depends_on=[minio_pvc],
        ),
        values={
            'fullnameOverride': "minio",
            'enabled': True,
            'mode': 'standalone',
            'auth': {
                'rootUser': 'minio',
                'rootPassword': pulumi.Output.all(minio_secret_key.result).apply(
                    lambda secret: secret[0]
                ),
            },
            'persistence': {
                'existingClaim': minio_pvc.metadata["name"],
            },
            "defaultBuckets":"thanos",
            'affinity': {
                'nodeAffinity': {
                    'requiredDuringSchedulingIgnoredDuringExecution': {
                        'nodeSelectorTerms': [
                            {
                                'matchExpressions': [
                                    {
                                        'key': 'node-role.kubernetes.io/storage',
                                        'operator': 'Exists',
                                    },
                                ],
                            },
                        ],
                    },
                },
            },
            'ingress': {
                'enabled': True,
                'tls': False,
                'hostname':'minio.local',
            },
            'resources': {
                'requests': {
                    'memory': '2Gi',
                    'cpu': '500m',
                },
                'limits': {
                    'memory': '4Gi',
                    'cpu': '2000m',
                },
            },
        },
    )

    pulumi.export(f"minio_secret_key", minio_secret_key.result)
    pulumi.export("minio_service_url", f"minio.{ns}.svc.cluster.local:9000")

    return minio
