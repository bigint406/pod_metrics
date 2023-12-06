from prometheus_client import Gauge, start_http_server
import os
import time
from kubernetes import client, config
import traceback
import yaml
import requests
requests.packages.urllib3.disable_warnings()
locust_metrics = [
    "avg_response_time",
    "current_rps",
    "current_fail_per_sec",
    "max_response_time",
    "ninety_ninth_response_time",
    "min_response_time",
    "ninetieth_response_time",
    "num_failures",
    "num_requests"
]
Metrics = {}
Metrics["pod_cpu_used_nano_persec"] = Gauge("pod_cpu_used_nano_persec", "pod cpu used nanosec persec from command 'kubectl get podmetrics'", ['namespace', "pod", "container"])
for i in locust_metrics:
    Metrics[i] = Gauge(i, "metrics from locust", ["name"])

metrics = locust_metrics.copy()
metrics.append("pod_cpu_used_nano_persec")

start_http_server(30124)

CI = 4
check_interval = 0
labels = None
labels = {}

config.load_kube_config()

while True:
    check_interval += 1
    if check_interval == CI:
        for i in metrics:
            labels[i] = Metrics[i]._metrics.copy()

    with client.ApiClient() as api_client:
        corev1 = client.CoreV1Api(api_client)
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
                        Metrics["pod_cpu_used_nano_persec"].labels(namespace=ns, pod=pod_name, container=container_name).set(cpu_used)
                
                        if check_interval == CI:
                            try:
                                del labels["pod_cpu_used_nano_persec"][(ns, pod_name, container_name)]
                            except KeyError:
                                pass

            except (TypeError, KeyError, yaml.parser.ParserError):
                traceback.print_exc()

    try:
        req = requests.request("get","http://10.112.48.121:8089/stats/requests")
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
        print(req)
    else:
        if req.status_code != 200:
            print(e)
            print(req)
        else:
            stats = req.json()["stats"]
            for i in stats:
                for j in locust_metrics:
                    Metrics[j].labels(name=i["safe_name"]).set(i[j])
                    if check_interval == CI:
                        try:
                            del labels[j][(i['safe_name'],)]
                        except KeyError as e:
                            pass

    if check_interval == CI:
        for k,v in labels.items():
            for i in v:
                Metrics[k].remove(*i)
        check_interval = 0
        labels.clear()
    time.sleep(5)
    

