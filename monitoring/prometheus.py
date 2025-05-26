import pulumi
import pulumi_kubernetes as k8s

def setup_prometheus(ns, minio_url, minio_secret_key, minio_release):
    prometheus_operator = k8s.helm.v3.Chart("prometheus-operator",
        k8s.helm.v3.ChartOpts(
            chart="kube-prometheus-stack",
            version="66.3.1",
            fetch_opts={"repo": "https://prometheus-community.github.io/helm-charts"},
            namespace=ns,
            values={
                'cleanPrometheusOperatorObjectNames': True,
                'defaultRules': {
                    'rules': {
                        'kubeProxy': False, # due to cillium
                        'kubeScheduler': False, # port exposed to localhost only
                        'kubeEtcd': False, # port exposed to localhost only
                        'kubeControllerManager': False, # port exposed to localhost only
                        'windows': False, # no windows nodes
                    },
                },
                'kubeEtcd': {
                    'enabled': False,
                },
                'kubeScheduler': {
                    'enabled': False,
                },
                'kubeControllerManager': {
                    'enabled': False,
                },
                'kubeProxy': {
                    'enabled': False,
                },
                'prometheus-node-exporter': {
                    'hostNetwork': False,
                    'env': {
                        'NODE_NAME': {
                            'valueFrom': {
                                'fieldRef': {
                                    'fieldPath': 'spec.nodeName',
                                },
                            },
                        },
                    },
                },
                'prometheus': {
                    'enabled': False,
                },
                'nodeExporter': {
                    'enabled': True,
                },
                'alertmanager': {
                    'enabled': False,
                },
                'grafana': {
                    'enabled': True,
                },
                'kubeStateMetrics': {
                    'enabled': True,
                },
            },
        )
    )

    prometheus_sa = k8s.core.v1.ServiceAccount("prometheus-sa",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="prometheus-sa",
            namespace=ns
        ),
    )

    thanos_config = k8s.core.v1.Secret("thanos-objstore-config",
        metadata={
            "name": "thanos-objstore-config",
            "namespace": ns,
        },
        string_data={
            "objstoreConfig": f"""type: s3
config:
    bucket: "thanos"
    endpoint: "{minio_url}"
    access_key: "minio"
    secret_key: "{minio_secret_key}"
    insecure: true
"""
        }
    )

    prometheus = k8s.apiextensions.CustomResource("prometheus",
        api_version="monitoring.coreos.com/v1",
        kind="Prometheus",
        metadata={
            "name": "prometheus",
            "namespace": ns,
        },
        spec={
            "serviceAccountName": prometheus_sa.metadata["name"],
            "replicas": 1,
            "version": "v2.26.0",
            "externalLabels": {
                "cluster": "k3s-cluster",
                "replica": "$(POD_NAME)",
                "prometheus_replica": "$(POD_NAME)"
            },
            "enableAdminAPI": True,
            "thanos": {
                "version": "v0.38.0",
                "image": "quay.io/thanos/thanos:v0.38.0",
                "objectStorageConfig": {
                    "key": "objstoreConfig",
                    "name": thanos_config.metadata["name"],
                },
            },
            "storage": {
                "volumeClaimTemplate": {
                    "spec": {
                        "storageClassName": "local-path",
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {
                            "requests": {
                                "storage": "10Gi"
                            }
                        }
                    }
                }
            },
            "serviceMonitorSelector": {
                "matchLabels": {
                    "release": "prometheus-operator"
                }
            },
            "podMonitorSelector": {
                "matchLabels": {
                    "release": "prometheus-operator"
                }
            },
            "ruleSelector": {
                "matchLabels": {
                    "release": "prometheus-operator"
                }
            },
            "resources": {
                "requests": {
                    "cpu": "500m",
                    "memory": "2Gi"
                },
                "limits": {
                    "cpu": "1",
                    "memory": "4Gi"
                }
            }
        },
        opts=pulumi.ResourceOptions(
            depends_on=[minio_release, prometheus_operator, thanos_config, prometheus_sa],
        ),
    )

    podmonitor = k8s.apiextensions.CustomResource("prometheus-podmonitor",
        opts=pulumi.ResourceOptions(
            depends_on=[prometheus] ,
        ),
        api_version="monitoring.coreos.com/v1",
        kind="PodMonitor",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="prometheus-autodiscovery",
            namespace=ns,
            labels={
                "placeholder": "exists",
            },
        ),
        spec={
            "namespaceSelector": {
                "any": True,
            },
            "selector": {
                "matchExpressions": [
                    {
                        "key": "monitoring-disabled",
                        "operator": "DoesNotExist",
                    }
                ]
            },
            "podMetricsEndpoints": [
                {
                    "port": "metrics",
                    "path": "/metrics",
                    "interval": "30s",
                    "scheme": "http",
                    "relabelings": [
                        {
                            "sourceLabels": ["__meta_kubernetes_pod_container_port_name"],
                            "action": "keep",
                            "regex": "metrics",
                        },
                        {
                            "targetLabel": "placeholder",
                            "replacement": "kube-dns",
                        },
                    ]
                }
            ]
        },
    )

    thanos_store_url = pulumi.Output.concat(
        "http://",
        prometheus.metadata["name"],
        "-thanos-discovery.",
        ns,
        ".svc.cluster.local:10902"
    )
    prometheus_url = pulumi.Output.concat(
        "http://",
        prometheus.metadata["name"],
        ".",
        ns,
        ".svc.cluster.local:9090"
    )

    pulumi.export("thanos_store_url", thanos_store_url)
    pulumi.export("prometheus_url", prometheus_url)

    return prometheus
