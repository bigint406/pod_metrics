from prometheus_client import Gauge, start_http_server
import os
import time
from kubernetes import client, config
import traceback
import yaml

start_http_server(30124)
pod_cpu_used_nano_persec = Gauge("pod_cpu_used_nano_persec", "pod cpu used nanosec persec from command 'kubectl get podmetrics'", ['namespace', "pod", "container"])

CI = 4
check_interval = 0
labels = None

config.load_kube_config()
api_client = client.api_client.ApiClient()
api_instance = client.AppsV1Api(api_client)
corev1 = client.CoreV1Api(api_client)

while True:
    check_interval += 1
    if check_interval == CI:
        labels = pod_cpu_used_nano_persec._metrics.copy()

    namespaces = corev1.list_namespace()
    for ns in namespaces.items:
        ns = ns.metadata.name
        with os.popen("kubectl get podmetrics -n %s -o yaml 2>&1" % ns) as f:
            try:
                data = yaml.safe_load(f)
                for po in data['items']:
                    if po['apiVersion'] == None:
                        break
                    pod_name = po['metadata']['name']
                    for con in po['containers']:
                        cpu_used = con['usage']['cpu']
                        if cpu_used != '0':
                            cpu_used = cpu_used[:-1]
                        container_name = con['name']
                        pod_cpu_used_nano_persec.labels(namespace=ns, pod=pod_name, container=container_name).set(cpu_used)
                
                        if check_interval == CI:
                            del labels[(ns, pod_name, container_name)]

            except (TypeError, KeyError, yaml.parser.ParserError):
                traceback.print_exc()

    if check_interval == CI:
        for i in labels:
            pod_cpu_used_nano_persec.remove(*i)
        check_interval = 0
    time.sleep(5)
    

