from prometheus_client import Gauge, start_http_server
import os
import time
from kubernetes import client, config
import traceback
import yaml
import requests
requests.packages.urllib3.disable_warnings()

Metrics = {}

locust_metrics = [
    "current_rps",
    "current_fail_per_sec",
    "num_failures",
    "num_requests"
]

metrics = locust_metrics.copy()
for i in locust_metrics:
    Metrics[i] = Gauge(i, "metrics from locust", ["name"])

metrics.append('ninety_fifth_response_time')
Metrics["ninety_fifth_response_time"] = Gauge("ninety_fifth_response_time", "metrics from locust", ["name"])

metrics.append('fiftieth_response_time')
Metrics["fiftieth_response_time"] = Gauge("fiftieth_response_time", "metrics from locust", ["name"])

metrics.append("pod_cpu_used_nano_persec")
Metrics["pod_cpu_used_nano_persec"] = Gauge("pod_cpu_used_nano_persec", "pod cpu used nanosec persec from command 'kubectl get podmetrics'", ['namespace', "pod", "container"])

metrics.append("pod_mem_used_KB")
Metrics["pod_mem_used_KB"] = Gauge("pod_mem_used_KB", "pod cpu used nanosec persec from command 'kubectl get podmetrics'", ['namespace', "pod", "container"])

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
                        mem_used = con['usage']['memory']
                        if mem_used != '0':
                            mem_used = mem_used[:-2]

                        container_name = con['name']
                        Metrics["pod_cpu_used_nano_persec"].labels(namespace=ns, pod=pod_name, container=container_name).set(cpu_used)
                        Metrics["pod_mem_used_KB"].labels(namespace=ns, pod=pod_name, container=container_name).set(mem_used)
                
                        if check_interval == CI:
                            try:
                                del labels["pod_cpu_used_nano_persec"][(ns, pod_name, container_name)]
                            except KeyError:
                                pass
                            try:
                                del labels["pod_mem_used_KB"][(ns, pod_name, container_name)]
                            except KeyError:
                                pass

            except (TypeError, KeyError, yaml.parser.ParserError):
                traceback.print_exc()

    # locust数据
    try:
        req = requests.request("get","http://10.112.48.121:8090/stats/requests")
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
    else:
        if req.status_code != 200:
            print(e)
            print(req)
        else:
            if req.json()["current_response_time_percentile_1"] is not None:
                Metrics["fiftieth_response_time"].labels(name="Aggregated").set(req.json()["current_response_time_percentile_1"])
                if check_interval == CI:
                    try:
                        del labels["fiftieth_response_time"][("Aggregated",)]
                    except KeyError as e:
                        pass
            if req.json()["current_response_time_percentile_2"] is not None:
                Metrics["ninety_fifth_response_time"].labels(name="Aggregated").set(req.json()["current_response_time_percentile_2"])
                if check_interval == CI:
                    try:
                        del labels["ninety_fifth_response_time"][("Aggregated",)]
                    except KeyError as e:
                        pass
            stats = req.json()["stats"]
            for i in stats:
                for j in locust_metrics:
                    n = i["safe_name"]
                    if n != "Aggregated":
                        continue
                    Metrics[j].labels(name=n).set(i[j])
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
    

